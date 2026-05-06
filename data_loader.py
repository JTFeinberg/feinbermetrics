import os
import sqlite3

import pandas as pd

DATABASE_PATH = "schedules.db"
CSV_PATH = "schedules.csv"
PITCHER_FIP_CSV_PATH = "pitcher_fip.csv"


def load_games() -> pd.DataFrame:
    if os.path.exists(DATABASE_PATH):
        return _load_from_database()
    if os.path.exists(CSV_PATH):
        return _load_from_csv()
    return pd.DataFrame()


def load_pitcher_fip() -> dict[str, float]:
    if not os.path.exists(PITCHER_FIP_CSV_PATH):
        return {}
    data = pd.read_csv(PITCHER_FIP_CSV_PATH)
    if "pitcher_name" not in data.columns:
        return {}
    return dict(zip(data["pitcher_name"], data["era"].astype(float)))


def _load_from_database() -> pd.DataFrame:
    connection = sqlite3.connect(DATABASE_PATH)
    games = pd.read_sql_query("SELECT * FROM games", connection)
    connection.close()
    return games


def _load_from_csv() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH)
