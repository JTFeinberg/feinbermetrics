import pandas as pd
import streamlit as st

from analytics import compute_season_summary
from sidebar import SEASON_PICKS_KEY, format_week_label, get_week_starts


def _render_add_pick_form(week_starts: list, week_labels: list, all_teams: list) -> None:
    with st.form("add_pick"):
        col1, col2 = st.columns(2)
        selected_week_label = col1.selectbox("Week", week_labels)
        selected_team = col2.selectbox("Team picked", all_teams)
        if st.form_submit_button("Add pick"):
            week_start = week_starts[week_labels.index(selected_week_label)]
            existing_weeks = {p["week_start"] for p in st.session_state[SEASON_PICKS_KEY]}
            if week_start in existing_weeks:
                st.warning("A pick already exists for that week. Remove it first.")
            else:
                st.session_state[SEASON_PICKS_KEY].append({
                    "week_label": selected_week_label,
                    "week_start": week_start,
                    "team": selected_team,
                })
                st.rerun()


def _render_picks_table(picks: list, games: pd.DataFrame) -> None:
    summary = compute_season_summary(picks, games)
    st.metric("Total wins this season", int(summary["W"].sum()))
    st.dataframe(summary, use_container_width=True, hide_index=True)

    with st.expander("Remove a pick"):
        for i, pick in enumerate(picks):
            col_label, col_btn = st.columns([5, 1])
            col_label.write(f"{pick['week_label']} — **{pick['team']}**")
            if col_btn.button("Remove", key=f"remove_pick_{i}"):
                st.session_state[SEASON_PICKS_KEY].pop(i)
                st.rerun()

    if st.button("Clear all picks"):
        st.session_state[SEASON_PICKS_KEY] = []
        st.rerun()


def render_season_tab(games: pd.DataFrame) -> None:
    st.subheader("Season picks tracker")
    st.caption("Log your weekly picks below to track your cumulative Biffle Ball score.")

    week_starts = get_week_starts(games)
    week_labels = [format_week_label(w) for w in week_starts]
    all_teams = sorted(games["team_name"].dropna().unique().tolist())

    if SEASON_PICKS_KEY not in st.session_state:
        st.session_state[SEASON_PICKS_KEY] = []

    _render_add_pick_form(week_starts, week_labels, all_teams)

    picks = st.session_state[SEASON_PICKS_KEY]
    if picks:
        _render_picks_table(picks, games)
    else:
        st.info("No picks logged yet.")
