from datetime import datetime

import pandas as pd
import streamlit as st

from data_loader import load_games
from persistence import load_picks, load_weather_flags, save_picks, save_weather_flags
from sidebar import (
    SEASON_PICKS_KEY,
    USED_TEAMS_KEY,
    WEATHER_FLAGS_KEY,
    get_week_starts,
    render_date_range,
    render_used_teams_tracker,
    render_week_picker,
)
from tabs import render_breakdown_tab, render_leaderboard_tab, render_season_tab

PASSWORD_SECRET_KEY = "app_password"


# ── Auth ──────────────────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    return st.session_state.get("authenticated", False)


def render_login_gate() -> None:
    st.set_page_config(page_title="Feinbermetrics", layout="centered")
    st.title("Feinbermetrics")
    st.caption("Biffle Ball weekly schedule analyzer")
    st.divider()
    password_input = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        if password_input == st.secrets.get(PASSWORD_SECRET_KEY, ""):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_default_week_index(week_starts: list[str]) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    index = next((i for i, w in enumerate(week_starts) if w <= today), 0)
    return min(index, len(week_starts) - 1)


def filter_games(games: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    return games[(games["game_date"] >= start_date) & (games["game_date"] <= end_date)].copy()


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(games: pd.DataFrame) -> tuple[str, str]:
    week_starts = get_week_starts(games)
    with st.sidebar:
        st.header("Feinbermetrics")
        st.divider()
        st.subheader("Week filter")
        use_week_picker = st.toggle("Use week picker", value=True)
        default_index = get_default_week_index(week_starts)
        start_date, end_date = (
            render_week_picker(week_starts, default_index) if use_week_picker
            else render_date_range(week_starts)
        )
        st.divider()
        render_used_teams_tracker(games)
    return start_date, end_date


# ── Main layout ───────────────────────────────────────────────────────────────

def render_main(games: pd.DataFrame, start_date: str, end_date: str) -> None:
    st.title("Feinbermetrics")
    st.caption("Biffle Ball weekly win probability analysis")

    tab_leaderboard, tab_breakdown, tab_season = st.tabs(
        ["Weekly leaderboard", "Game breakdown", "Season tracker"]
    )
    week_games = filter_games(games, start_date, end_date)
    weather_flags = st.session_state.get(WEATHER_FLAGS_KEY, set())

    with tab_leaderboard:
        render_leaderboard_tab(week_games, start_date, end_date, weather_flags)
    with tab_breakdown:
        render_breakdown_tab(week_games, start_date, end_date, weather_flags)
    with tab_season:
        render_season_tab(games)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not is_authenticated():
        render_login_gate()
        return

    st.set_page_config(page_title="Feinbermetrics", layout="wide")

    if not st.session_state.get("picks_initialized"):
        saved = load_picks()
        st.session_state[USED_TEAMS_KEY] = set(saved["used_teams"])
        st.session_state[SEASON_PICKS_KEY] = saved["season_picks"]
        st.session_state[WEATHER_FLAGS_KEY] = load_weather_flags()
        st.session_state["picks_initialized"] = True

    games = load_games()

    if games.empty:
        st.error("No schedule data found. Run `python fetch_schedules.py` then `python export_csv.py`.")
        return

    start_date, end_date = render_sidebar(games)
    render_main(games, start_date, end_date)

    save_picks(
        used_teams=st.session_state.get(USED_TEAMS_KEY, set()),
        season_picks=st.session_state.get(SEASON_PICKS_KEY, []),
    )
    save_weather_flags(st.session_state.get(WEATHER_FLAGS_KEY, set()))


if __name__ == "__main__":
    main()
