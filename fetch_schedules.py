import json
import sqlite3
import time
from datetime import datetime, timedelta

import requests

FANGRAPHS_SCHEDULE_URL = "https://www.fangraphs.com/api/scores/season-schedule"
FANGRAPHS_BASE_URL = "https://www.fangraphs.com/scores/season-schedule-and-results"
SEASON = 2026
TEAM_ID_MIN = 1
TEAM_ID_MAX = 30
DATABASE_PATH = "schedules.db"
REQUEST_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 15

# Headers that match what Chrome sends when visiting FanGraphs in a browser.
# Without these, Cloudflare returns 403 even though the URL is public.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.fangraphs.com/scores/season-schedule-and-results",
    "Origin": "https://www.fangraphs.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Connection": "keep-alive",
}


def get_monday_of_week(date_string: str) -> str:
    game_date = datetime.strptime(date_string, "%Y-%m-%d")
    days_since_monday = game_date.weekday()
    monday = game_date - timedelta(days=days_since_monday)
    return monday.strftime("%Y-%m-%d")


def create_session() -> requests.Session:
    """
    Opens a session that visits FanGraphs first so Cloudflare sets cookies,
    then all subsequent API calls include those cookies automatically.
    """
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    print("Establishing browser session with FanGraphs...")
    warmup = session.get(FANGRAPHS_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    warmup.raise_for_status()
    print(f"Session ready (status {warmup.status_code}, {len(session.cookies)} cookies)\n")
    time.sleep(1.0)
    return session


def fetch_team_schedule(session: requests.Session, team_id: int) -> list:
    params = {"season": SEASON, "teamid": team_id}
    response = session.get(
        FANGRAPHS_SCHEDULE_URL,
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["schedule"]


def normalize_game(raw_game: dict, team_id: int) -> dict:
    game_date = raw_game.get("GameDateParam", "")
    is_home = raw_game.get("HomeTeamId") == team_id
    team_name = raw_game.get("HomeTeamName") if is_home else raw_game.get("AwayTeamName")

    raw_win_prob = raw_game.get("TeamWinProb")
    win_probability = raw_win_prob if (raw_win_prob is not None and raw_win_prob >= 0) else None

    team_runs = raw_game.get("TeamRuns", "")
    opp_runs = raw_game.get("OppRuns", "")
    score = f"{team_runs}-{opp_runs}" if team_runs != "" and opp_runs != "" else None

    result = raw_game.get("Result") or None

    return {
        "game_id": str(raw_game.get("GameId", "")),
        "team_id": team_id,
        "team_name": team_name,
        "game_date": game_date,
        "home_team": raw_game.get("HomeTeamName", ""),
        "away_team": raw_game.get("AwayTeamName", ""),
        "is_home": 1 if is_home else 0,
        "opponent": raw_game.get("Opponent", ""),
        "win_probability": win_probability,
        "result": result,
        "score": score,
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

    session = create_session()
    total_games = 0

    for team_id in range(TEAM_ID_MIN, TEAM_ID_MAX + 1):
        try:
            raw_schedule = fetch_team_schedule(session, team_id)

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
