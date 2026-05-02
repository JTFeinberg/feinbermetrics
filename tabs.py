import pandas as pd
import streamlit as st

from analytics import compute_biffle_metrics, compute_season_summary
from sidebar import USED_TEAMS_KEY, SEASON_PICKS_KEY, WEATHER_FLAGS_KEY, format_week_label, get_week_starts

GAMES_WEEK_MAX = 7


def render_leaderboard_tab(
    week_games: pd.DataFrame,
    start_date: str,
    end_date: str,
    weather_flags: set,
) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    used_teams = st.session_state.get(USED_TEAMS_KEY, set())
    metrics = compute_biffle_metrics(week_games, excluded_game_ids=weather_flags)
    available = metrics[~metrics["Team"].isin(used_teams)].copy()
    used_rows = metrics[metrics["Team"].isin(used_teams)].copy()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Teams available", len(available))
    col2.metric("Top Biffle Score", f"{available['Biffle Score'].max():.1f}" if not available.empty else "—")
    col3.metric("Max games", int(available["Games"].max()) if not available.empty else "—")
    col4.metric("Date range", f"{start_date} \u2192 {end_date}")

    st.subheader("Available teams")
    st.caption(
        "**Biffle Score** (0–10) = Expected Wins scaled to a weekly max of 7 games. "
        "**Expected Wins** = sum of win probabilities. Weather-flagged games are excluded."
    )
    _show_metrics_table(available, start_date, end_date, "leaderboard_available")

    if not used_rows.empty:
        with st.expander(f"Already used ({len(used_rows)} teams)"):
            _show_metrics_table(used_rows, start_date, end_date, "leaderboard_used")


def _show_metrics_table(df: pd.DataFrame, start_date: str, end_date: str, key: str) -> None:
    display = df[["Team", "Biffle Score", "Games", "Home", "Away", "Expected Wins",
                  "Avg Win%", "Probs Available", "Actual W", "Games Played"]].copy()
    st.dataframe(
        display.style.format({
            "Biffle Score": "{:.1f}",
            "Expected Wins": "{:.2f}",
            "Avg Win%": lambda v: f"{v:.1%}" if v is not None else "—",
            "Actual W": lambda v: str(int(v)) if v is not None else "—",
            "Games Played": lambda v: str(int(v)) if v is not None else "—",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        file_name=f"biffle_leaderboard_{start_date}_{end_date}.csv",
        mime="text/csv",
        key=f"dl_{key}",
    )


def render_breakdown_tab(
    week_games: pd.DataFrame,
    start_date: str,
    end_date: str,
    weather_flags: set,
) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    selected_team = st.selectbox("Select team", sorted(week_games["team_name"].dropna().unique()))
    team_games = week_games[week_games["team_name"] == selected_team].copy()

    team_games["Win Prob"] = team_games["win_probability"].apply(
        lambda p: f"{p:.1%}" if pd.notna(p) else "\u2014"
    )
    team_games["H/A"] = team_games["is_home"].map({1: "Home", 0: "Away"})
    team_games["⛈ Weather"] = team_games["game_id"].isin(weather_flags)

    display_cols = ["game_id", "game_date", "H/A", "opponent", "team_pitcher",
                    "opp_pitcher", "Win Prob", "result", "score", "⛈ Weather"]
    has_pitchers = "team_pitcher" in team_games.columns

    renamed = team_games.rename(columns={
        "game_date": "Date", "opponent": "Opponent",
        "team_pitcher": "Our Pitcher", "opp_pitcher": "Opp Pitcher",
        "result": "Result", "score": "Score",
    })

    editable_cols = ["Date", "H/A", "Opponent", "Win Prob", "Result", "Score"]
    shown_cols = ["game_id", "Date", "H/A", "Opponent", "Win Prob", "Result", "Score", "⛈ Weather"]
    if has_pitchers:
        editable_cols = ["Date", "H/A", "Opponent", "Our Pitcher", "Opp Pitcher", "Win Prob", "Result", "Score"]
        shown_cols = ["game_id", "Date", "H/A", "Opponent", "Our Pitcher", "Opp Pitcher",
                      "Win Prob", "Result", "Score", "⛈ Weather"]

    edited = st.data_editor(
        renamed[shown_cols],
        column_config={
            "game_id": None,
            "⛈ Weather": st.column_config.CheckboxColumn("⛈ Weather", help="Flag this game as a weather risk — excludes it from Expected Wins"),
        },
        disabled=editable_cols,
        use_container_width=True,
        hide_index=True,
        key=f"breakdown_{selected_team}",
    )

    team_game_ids = set(team_games["game_id"].tolist())
    flagged_this_team = set(edited[edited["⛈ Weather"]]["game_id"].tolist())
    updated_flags = (weather_flags - team_game_ids) | flagged_this_team
    if updated_flags != weather_flags:
        st.session_state[WEATHER_FLAGS_KEY] = updated_flags
        st.rerun()

    st.download_button(
        f"Download {selected_team} CSV",
        team_games.to_csv(index=False),
        file_name=f"{selected_team.replace(' ', '_')}_{start_date}_{end_date}.csv",
        mime="text/csv",
    )


def render_season_tab(games: pd.DataFrame) -> None:
    st.subheader("Season picks tracker")
    st.caption("Log your weekly picks below to track your cumulative Biffle Ball score.")

    from app import get_week_starts
    week_starts = get_week_starts(games)
    week_labels = [format_week_label(w) for w in week_starts]
    all_teams = sorted(games["team_name"].dropna().unique().tolist())

    if SEASON_PICKS_KEY not in st.session_state:
        st.session_state[SEASON_PICKS_KEY] = []

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

    picks = st.session_state[SEASON_PICKS_KEY]
    if picks:
        summary = compute_season_summary(picks, games)
        st.metric("Total wins this season", int(summary["W"].sum()))
        st.dataframe(summary, use_container_width=True, hide_index=True)
        if st.button("Clear all picks"):
            st.session_state[SEASON_PICKS_KEY] = []
            st.rerun()
    else:
        st.info("No picks logged yet.")
