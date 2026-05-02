import os
import sqlite3

import pandas as pd

DATABASE_PATH = "schedules.db"
CSV_PATH = "schedules.csv"


def load_games() -> pd.DataFrame:
    if os.path.exists(DATABASE_PATH):
        return _load_from_database()
    if os.path.exists(CSV_PATH):
        return _load_from_csv()
    return pd.DataFrame()


def _load_from_database() -> pd.DataFrame:
    connection = sqlite3.connect(DATABASE_PATH)
    games = pd.read_sql_query("SELECT * FROM games", connection)
    connection.close()
    return games


def _load_from_csv() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH)
