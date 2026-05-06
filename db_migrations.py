import sqlite3


def migrate(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "team_pitcher_id", "INTEGER")
    _add_column_if_missing(connection, "opp_pitcher_id", "INTEGER")


def _add_column_if_missing(
    connection: sqlite3.Connection, column: str, column_type: str
) -> None:
    existing = {row[1] for row in connection.execute("PRAGMA table_info(games)").fetchall()}
    if column not in existing:
        connection.execute(f"ALTER TABLE games ADD COLUMN {column} {column_type}")
        connection.commit()
        print(f"Migrated: added column '{column}' to games table")
