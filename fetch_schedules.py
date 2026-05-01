import json
import sqlite3
import time
from datetime import datetime, timedelta

import requests

FANGRAPHS_SCHEDULE_URL = "https://www.fangraphs.com/api/scores/season-schedule"
SEASON = 2026
TEAM_ID_MIN = 1
TEAM_ID_MAX = 30
DATABASE_PATH = "schedules.db"
REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 10


def get_monday_of_week(date_string: str) -> str:
    game_date = datetime.strptime(date_string, "%Y-%m-%d")
    days_since_monday = game_date.weekday()
    monday = game_date - timedelta(days=days_since_monday)
    return monday.strftime("%Y-%m-%d")


def fetch_team_schedule(team_id: int) -> list:
    params = {"season": SEASON, "teamid": team_id}
    response = requests.get(
        FANGRAPHS_SCHEDULE_URL,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    return response.json()


def normalize_game(raw_game: dict, team_id: int) -> dict:
    raw_date = raw_game.get("Date", raw_game.get("GameDate", ""))
    game_date = str(raw_date)[:10] if raw_date else ""

    team_name = raw_game.get("Team", raw_game.get("TeamName", ""))
    home_team = raw_game.get("HomeTeam", "")

    return {
        "game_id": str(raw_game.get("GameId", raw_game.get("gameId", ""))),
        "team_id": team_id,
        "team_name": team_name,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": raw_game.get("AwayTeam", ""),
        "is_home": 1 if team_name == home_team else 0,
        "opponent": raw_game.get("Opponent", raw_game.get("OppTeam", "")),
        "win_probability": raw_game.get(
            "WinProbability", raw_game.get("PreGameWinProb", None)
        ),
        "result": raw_game.get("Result", raw_game.get("WL", None)),
        "score": raw_game.get("Score", None),
        "week_start": get_monday_of_week(game_date) if game_date else "",
    }


def create_schema(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id          TEXT,
            team_id          INTEGER,
            team_name        TEXT,
            game_date        TEXT,
            home_team        TEXT,
            away_team        TEXT,
            is_home          INTEGER,
            opponent         TEXT,
            win_probability  REAL,
            result           TEXT,
            score            TEXT,
            week_start       TEXT,
            PRIMARY KEY (game_id, team_id)
        )
    """)
    connection.commit()


def upsert_games(connection: sqlite3.Connection, games: list) -> None:
    connection.executemany(
        """
        INSERT OR REPLACE INTO games
            (game_id, team_id, team_name, game_date, home_team, away_team,
             is_home, opponent, win_probability, result, score, week_start)
        VALUES
            (:game_id, :team_id, :team_name, :game_date, :home_team, :away_team,
             :is_home, :opponent, :win_probability, :result, :score, :week_start)
        """,
        games,
    )
    connection.commit()


def print_sample_record(raw_schedule: list) -> None:
    sample = raw_schedule[0] if raw_schedule else {}
    print("Sample raw record from FanGraphs (use this to verify field mapping):")
    print(json.dumps(sample, indent=2))
    print()


def main() -> None:
    connection = sqlite3.connect(DATABASE_PATH)
    create_schema(connection)

    total_games = 0
    for team_id in range(TEAM_ID_MIN, TEAM_ID_MAX + 1):
        try:
            raw_schedule = fetch_team_schedule(team_id)

            if team_id == TEAM_ID_MIN and raw_schedule:
                print_sample_record(raw_schedule)

            games = [normalize_game(game, team_id) for game in raw_schedule]
            upsert_games(connection, games)
            total_games += len(games)
            print(f"Team {team_id:>2}: {len(games):>3} games loaded")

            time.sleep(REQUEST_DELAY_SECONDS)

        except requests.HTTPError as error:
            print(f"HTTP error fetching team {team_id}: {error}")
        except requests.Timeout:
            print(f"Timeout fetching team {team_id} — skipping")
        except (KeyError, ValueError, TypeError) as error:
            print(f"Parse error for team {team_id}: {error}")

    connection.close()
    print(f"\nDone. {total_games} game records written to {DATABASE_PATH}")


if __name__ == "__main__":
    main()
