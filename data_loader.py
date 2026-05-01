import os
import sqlite3
import time

import pandas as pd
import requests
import streamlit as st

FANGRAPHS_SCHEDULE_URL = "https://www.fangraphs.com/api/scores/season-schedule"
FANGRAPHS_BASE_URL = "https://www.fangraphs.com/scores/season-schedule-and-results"
DATABASE_PATH = "schedules.db"
SEASON = 2026
TEAM_ID_MIN = 1
TEAM_ID_MAX = 30
REQUEST_DELAY_SECONDS = 0.4
REQUEST_TIMEOUT_SECONDS = 15
CACHE_TTL_SECONDS = 12 * 3600

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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


def load_games() -> pd.DataFrame:
    if os.path.exists(DATABASE_PATH):
        return _load_from_database()
    return _fetch_all_teams_live()


def _load_from_database() -> pd.DataFrame:
    connection = sqlite3.connect(DATABASE_PATH)
    games = pd.read_sql_query("SELECT * FROM games", connection)
    connection.close()
    return games


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Fetching live schedule data from FanGraphs...")
def _fetch_all_teams_live() -> pd.DataFrame:
    session = _create_browser_session()
    all_games = []
    for team_id in range(TEAM_ID_MIN, TEAM_ID_MAX + 1):
        try:
            raw_games = _fetch_single_team(session, team_id)
            all_games.extend(_normalize_team_games(raw_games, team_id))
            time.sleep(REQUEST_DELAY_SECONDS)
        except requests.HTTPError:
            pass
        except (KeyError, ValueError, TypeError):
            pass
    return pd.DataFrame(all_games)


def _create_browser_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    session.get(FANGRAPHS_BASE_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    time.sleep(1.0)
    return session


def _fetch_single_team(session: requests.Session, team_id: int) -> list:
    params = {"season": SEASON, "teamid": team_id}
    response = session.get(FANGRAPHS_SCHEDULE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()["schedule"]


def _normalize_team_games(raw_games: list, team_id: int) -> list:
    from datetime import datetime, timedelta

    def get_monday(date_string: str) -> str:
        game_date = datetime.strptime(date_string, "%Y-%m-%d")
        return (game_date - timedelta(days=game_date.weekday())).strftime("%Y-%m-%d")

    normalized = []
    for raw in raw_games:
        game_date = raw.get("GameDateParam", "")
        is_home = raw.get("HomeTeamId") == team_id
        raw_prob = raw.get("TeamWinProb")
        win_probability = raw_prob if (raw_prob is not None and raw_prob >= 0) else None
        team_runs = raw.get("TeamRuns", "")
        opp_runs = raw.get("OppRuns", "")
        normalized.append({
            "game_id": str(raw.get("GameId", "")),
            "team_id": team_id,
            "team_name": raw.get("HomeTeamName") if is_home else raw.get("AwayTeamName"),
            "game_date": game_date,
            "home_team": raw.get("HomeTeamName", ""),
            "away_team": raw.get("AwayTeamName", ""),
            "is_home": 1 if is_home else 0,
            "opponent": raw.get("Opponent", ""),
            "win_probability": win_probability,
            "result": raw.get("Result") or None,
            "score": f"{team_runs}-{opp_runs}" if team_runs != "" and opp_runs != "" else None,
            "week_start": get_monday(game_date) if game_date else "",
        })
    return normalized


def clear_live_cache() -> None:
    _fetch_all_teams_live.clear()
