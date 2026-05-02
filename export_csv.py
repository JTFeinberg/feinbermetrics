import sqlite3

import pandas as pd

DATABASE_PATH = "schedules.db"
CSV_PATH = "schedules.csv"

connection = sqlite3.connect(DATABASE_PATH)
games = pd.read_sql_query("SELECT * FROM games", connection)
connection.close()
games.to_csv(CSV_PATH, index=False)
print(f"Exported {len(games)} rows to {CSV_PATH}")
