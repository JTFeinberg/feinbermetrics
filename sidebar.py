from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

USED_TEAMS_KEY = "used_teams"
SEASON_PICKS_KEY = "season_picks"
WEATHER_FLAGS_KEY = "weather_flags"


def get_week_starts(games: pd.DataFrame) -> list[str]:
    return sorted(games["week_start"].dropna().unique().tolist())


def render_week_picker(week_starts: list[str], default_index: int) -> tuple[str, str]:
    labels = [format_week_label(w) for w in week_starts]
    selected = st.selectbox("Select week", labels, index=default_index)
    week_start = week_starts[labels.index(selected)]
    week_end = (datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
    return week_start, week_end


def render_date_range(week_starts: list[str]) -> tuple[str, str]:
    min_date = datetime.strptime(week_starts[0], "%Y-%m-%d").date()
    max_date = (datetime.strptime(week_starts[-1], "%Y-%m-%d") + timedelta(days=6)).date()
    date_range = st.date_input("Custom range", value=(min_date, max_date),
                               min_value=min_date, max_value=max_date)
    if len(date_range) == 2:
        return date_range[0].strftime("%Y-%m-%d"), date_range[1].strftime("%Y-%m-%d")
    single = date_range[0].strftime("%Y-%m-%d")
    return single, single


def render_used_teams_tracker(games: pd.DataFrame) -> None:
    st.subheader("Used teams")
    st.caption("Check off teams you've already picked this season.")
    if USED_TEAMS_KEY not in st.session_state:
        st.session_state[USED_TEAMS_KEY] = set()

    for team in sorted(games["team_name"].dropna().unique().tolist()):
        checked = team in st.session_state[USED_TEAMS_KEY]
        if st.checkbox(team, value=checked, key=f"used_{team}"):
            st.session_state[USED_TEAMS_KEY].add(team)
        else:
            st.session_state[USED_TEAMS_KEY].discard(team)


def format_week_label(week_start: str) -> str:
    monday = datetime.strptime(week_start, "%Y-%m-%d")
    sunday = monday + timedelta(days=6)
    return f"Week of {monday.strftime('%b %d')} \u2013 {sunday.strftime('%b %d, %Y')}"
