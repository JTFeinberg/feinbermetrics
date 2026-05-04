import pandas as pd
import streamlit as st

from analytics import compute_biffle_metrics, compute_season_summary
from sidebar import USED_TEAMS_KEY, SEASON_PICKS_KEY, WEATHER_FLAGS_KEY, format_week_label, get_week_starts
from weather import RAIN_WARNING_THRESHOLD, get_rain_probabilities


# ── Team breakdown dialog ──────────────────────────────────────────────────────

@st.dialog("Game breakdown", width="large")
def _show_team_dialog(team_name: str, week_games: pd.DataFrame, weather_flags: set) -> None:
    rain_by_game = get_rain_probabilities(week_games)
    _render_team_game_table(team_name, week_games, weather_flags, rain_by_game)


# ── Leaderboard tab ────────────────────────────────────────────────────────────

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
        "**Biffle Score** (0–10) = Expected Wins on a weekly scale. "
        "Click any row to see that team's full game breakdown."
    )
    _show_metrics_table(available, week_games, weather_flags, start_date, end_date, "available")

    if not used_rows.empty:
        with st.expander(f"Already used ({len(used_rows)} teams)"):
            _show_metrics_table(used_rows, week_games, weather_flags, start_date, end_date, "used")


def _show_metrics_table(
    df: pd.DataFrame,
    week_games: pd.DataFrame,
    weather_flags: set,
    start_date: str,
    end_date: str,
    key: str,
) -> None:
    display = df[["Team", "Biffle Score", "Games", "DH", "Home", "Away",
                  "Expected Wins", "Avg Win%", "Confidence", "Actual W", "Games Played"]].copy()
    event = st.dataframe(
        display.style.format({
            "Biffle Score": "{:.1f}",
            "Expected Wins": "{:.2f}",
            "Avg Win%": lambda v: f"{v:.1%}" if v is not None else "—",
            "DH": lambda v: f"⚡ {int(v)}" if v and int(v) > 0 else "—",
            "Actual W": lambda v: str(int(v)) if v is not None else "—",
            "Games Played": lambda v: str(int(v)) if v is not None else "—",
        }, na_rep="—"),
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key=f"tbl_{key}",
    )
    if event.selection.rows:
        selected_team = display.iloc[event.selection.rows[0]]["Team"]
        _show_team_dialog(selected_team, week_games, weather_flags)

    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        file_name=f"biffle_leaderboard_{start_date}_{end_date}.csv",
        mime="text/csv",
        key=f"dl_{key}",
    )


# ── Breakdown tab ──────────────────────────────────────────────────────────────

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

    with st.spinner("Fetching weather forecast..."):
        rain_by_game = get_rain_probabilities(week_games)

    _render_team_game_table(selected_team, week_games, weather_flags, rain_by_game)

    team_games = week_games[week_games["team_name"] == selected_team]
    st.download_button(
        f"Download {selected_team} CSV",
        team_games.to_csv(index=False),
        file_name=f"{selected_team.replace(' ', '_')}_{start_date}_{end_date}.csv",
        mime="text/csv",
    )


def _render_team_game_table(
    team_name: str,
    week_games: pd.DataFrame,
    weather_flags: set,
    rain_by_game: dict,
) -> None:
    team_games = week_games[week_games["team_name"] == team_name].copy()

    team_games["Win Prob"] = team_games["win_probability"].apply(
        lambda p: f"{p:.1%}" if pd.notna(p) else "\u2014"
    )
    team_games["H/A"] = team_games["is_home"].map({1: "Home", 0: "Away"})
    team_games["⛈ Weather"] = team_games["game_id"].isin(weather_flags)
    team_games["🌧 Rain%"] = team_games["game_id"].map(
        lambda gid: _format_rain(rain_by_game.get(gid))
    )
    if "dh" in team_games.columns:
        team_games["DH"] = team_games["dh"].apply(lambda x: "⚡" if x == 1 else "")

    has_pitchers = "team_pitcher" in team_games.columns
    has_dh = "dh" in team_games.columns

    renamed = team_games.rename(columns={
        "game_date": "Date", "opponent": "Opponent",
        "team_pitcher": "Our Pitcher", "opp_pitcher": "Opp Pitcher",
        "result": "Result", "score": "Score",
    })

    base_cols = ["game_id", "Date", "H/A", "Opponent", "Win Prob", "🌧 Rain%", "Result", "Score"]
    if has_pitchers:
        base_cols = ["game_id", "Date", "H/A", "Opponent", "Our Pitcher", "Opp Pitcher",
                     "Win Prob", "🌧 Rain%", "Result", "Score"]
    if has_dh:
        base_cols = base_cols[:-2] + ["DH"] + base_cols[-2:]
    shown_cols = base_cols + ["⛈ Weather"]
    editable_cols = [c for c in shown_cols if c not in ("game_id", "⛈ Weather")]

    edited = st.data_editor(
        renamed[shown_cols],
        column_config={
            "game_id": None,
            "⛈ Weather": st.column_config.CheckboxColumn(
                "⛈ Weather",
                help="Exclude this game from Expected Wins (weather risk)",
            ),
        },
        disabled=editable_cols,
        use_container_width=True,
        hide_index=True,
        key=f"breakdown_{team_name}",
    )

    team_game_ids = set(team_games["game_id"].tolist())
    flagged = set(edited[edited["⛈ Weather"]]["game_id"].tolist())
    updated_flags = (weather_flags - team_game_ids) | flagged
    if updated_flags != weather_flags:
        st.session_state[WEATHER_FLAGS_KEY] = updated_flags
        st.rerun()


def _format_rain(pct: int | None) -> str:
    if pct is None:
        return "—"
    warning = " ⚠️" if pct >= RAIN_WARNING_THRESHOLD else ""
    return f"{pct}%{warning}"


# ── Season tab ─────────────────────────────────────────────────────────────────

def render_season_tab(games: pd.DataFrame) -> None:
    st.subheader("Season picks tracker")
    st.caption("Log your weekly picks below to track your cumulative Biffle Ball score.")

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
    else:
        st.info("No picks logged yet.")
