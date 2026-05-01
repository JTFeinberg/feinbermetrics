import sqlite3
from datetime import datetime, timedelta
from functools import reduce
from operator import mul

import pandas as pd
import streamlit as st

DATABASE_PATH = "schedules.db"
PASSWORD_SECRET_KEY = "app_password"


def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def render_login_gate() -> None:
    st.set_page_config(page_title="Feinbermetrics", layout="centered")
    st.title("Feinbermetrics")
    st.markdown("MLB Schedule Win Probability Analyzer")
    st.divider()

    password_input = st.text_input("Password", type="password")

    if st.button("Sign in", type="primary"):
        expected = st.secrets.get(PASSWORD_SECRET_KEY, "")
        if password_input == expected:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")


def get_week_starts(connection: sqlite3.Connection) -> list:
    result = pd.read_sql_query(
        "SELECT DISTINCT week_start FROM games ORDER BY week_start", connection
    )
    return result["week_start"].tolist()


def load_games_for_range(
    connection: sqlite3.Connection, start_date: str, end_date: str
) -> pd.DataFrame:
    query = """
        SELECT
            game_id, game_date, home_team, away_team, week_start,
            team_id, team_name, is_home, opponent, win_probability, result, score
        FROM games
        WHERE game_date >= ? AND game_date <= ?
        ORDER BY game_date ASC
    """
    return pd.read_sql_query(query, connection, params=(start_date, end_date))


def compute_sweep_probabilities(games: pd.DataFrame) -> pd.DataFrame:
    team_rows = []
    for team_name, team_games in games.groupby("team_name"):
        probabilities = team_games["win_probability"].dropna().tolist()
        game_count = len(team_games)

        sweep_probability = reduce(mul, probabilities, 1.0) if probabilities else None
        average_win_probability = (
            sum(probabilities) / len(probabilities) if probabilities else None
        )

        team_rows.append({
            "Team": team_name,
            "Games": game_count,
            "Avg Win Prob": average_win_probability,
            "Sweep Probability": sweep_probability,
        })

    return (
        pd.DataFrame(team_rows)
        .sort_values("Sweep Probability", ascending=False)
        .reset_index(drop=True)
    )


def format_week_label(week_start: str) -> str:
    monday = datetime.strptime(week_start, "%Y-%m-%d")
    sunday = monday + timedelta(days=6)
    return f"Week of {monday.strftime('%b %d')} \u2013 {sunday.strftime('%b %d, %Y')}"


def render_sidebar_filters(week_starts: list) -> tuple[str, str]:
    with st.sidebar:
        st.header("Filters")
        use_week_picker = st.toggle("Use week picker", value=True)

        if use_week_picker:
            return render_week_picker(week_starts)
        return render_date_range_picker(week_starts)


def render_week_picker(week_starts: list) -> tuple[str, str]:
    week_labels = [format_week_label(w) for w in week_starts]
    today = datetime.today().strftime("%Y-%m-%d")

    default_index = next(
        (i for i, w in enumerate(week_starts) if w <= today), 0
    )
    default_index = min(default_index, len(week_labels) - 1)

    selected_label = st.selectbox("Select week (Mon\u2013Sun)", week_labels, index=default_index)
    selected_week_start = week_starts[week_labels.index(selected_label)]
    selected_week_end = (
        datetime.strptime(selected_week_start, "%Y-%m-%d") + timedelta(days=6)
    ).strftime("%Y-%m-%d")

    return selected_week_start, selected_week_end


def render_date_range_picker(week_starts: list) -> tuple[str, str]:
    min_date = datetime.strptime(week_starts[0], "%Y-%m-%d").date()
    max_date = (
        datetime.strptime(week_starts[-1], "%Y-%m-%d") + timedelta(days=6)
    ).date()

    date_range = st.date_input(
        "Custom date range", value=(min_date, max_date),
        min_value=min_date, max_value=max_date,
    )

    if len(date_range) == 2:
        return date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d")
    single_date = date_range[0].strftime("%Y-%m-%d")
    return single_date, single_date


def render_leaderboard(games: pd.DataFrame, start_date: str, end_date: str) -> None:
    st.subheader("Sweep probability leaderboard")
    st.caption(
        "P(sweep) = product of all win probabilities for a team's games in the selected window. "
        "Higher = more likely to win every game that week."
    )

    sweep_df = compute_sweep_probabilities(games)

    st.dataframe(
        sweep_df.style.format(
            {"Avg Win Prob": "{:.1%}", "Sweep Probability": "{:.1%}"},
            na_rep="\u2014",
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download leaderboard CSV",
        sweep_df.to_csv(index=False),
        file_name=f"sweep_leaderboard_{start_date}_{end_date}.csv",
        mime="text/csv",
    )


def render_game_breakdown(games: pd.DataFrame, start_date: str, end_date: str) -> None:
    st.subheader("Game-by-game breakdown")

    selected_team = st.selectbox("Select team", sorted(games["team_name"].unique()))
    team_games = games[games["team_name"] == selected_team].copy()
    team_games["Win Prob"] = team_games["win_probability"].apply(
        lambda prob: f"{prob:.1%}" if pd.notna(prob) else "\u2014"
    )

    display_df = team_games.rename(columns={
        "game_date": "Date",
        "home_team": "Home",
        "away_team": "Away",
        "result": "Result",
        "score": "Score",
    })[["Date", "Home", "Away", "Win Prob", "Result", "Score"]]

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.download_button(
        f"Download {selected_team} CSV",
        team_games.to_csv(index=False),
        file_name=f"{selected_team.replace(' ', '_')}_{start_date}_{end_date}.csv",
        mime="text/csv",
    )


def main() -> None:
    if not is_authenticated():
        render_login_gate()
        return

    st.set_page_config(page_title="Feinbermetrics", layout="wide")
    st.title("Feinbermetrics")
    st.caption("MLB schedule win probability analysis")

    try:
        connection = sqlite3.connect(DATABASE_PATH)
    except sqlite3.OperationalError as error:
        st.error(f"Could not open database: {error}. Run fetch_schedules.py first.")
        return

    week_starts = get_week_starts(connection)

    if not week_starts:
        st.warning("No schedule data found. Run `python fetch_schedules.py` first.")
        connection.close()
        return

    start_date, end_date = render_sidebar_filters(week_starts)
    games = load_games_for_range(connection, start_date, end_date)
    connection.close()

    if games.empty:
        st.info("No games found for the selected date range.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Games in range", games["game_id"].nunique())
    col2.metric("Teams with games", games["team_name"].nunique())
    col3.metric("Date range", f"{start_date}  \u2192  {end_date}")

    st.divider()
    render_leaderboard(games, start_date, end_date)
    st.divider()
    render_game_breakdown(games, start_date, end_date)


if __name__ == "__main__":
    main()
