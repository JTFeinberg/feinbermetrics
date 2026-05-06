import pandas as pd
import streamlit as st

from analytics import compute_biffle_metrics, compute_recent_form
from sidebar import USED_TEAMS_KEY, WEATHER_FLAGS_KEY, format_week_label, get_week_starts
from weather import RAIN_WARNING_THRESHOLD, get_rain_probabilities

DIALOG_TEAM_KEY = "_open_dialog_team"
TABLE_COUNTER_KEY = "_tbl_counter"


# ── Team breakdown dialog ──────────────────────────────────────────────────────

@st.dialog("Game breakdown", width="large")
def _show_team_dialog(team_name: str, week_games: pd.DataFrame, weather_flags: set, pitcher_fip: dict) -> None:
    rain_by_game = get_rain_probabilities(week_games)
    _render_team_game_table(team_name, week_games, weather_flags, rain_by_game, pitcher_fip)


# ── Leaderboard tab ────────────────────────────────────────────────────────────

def render_leaderboard_tab(
    week_games: pd.DataFrame,
    start_date: str,
    end_date: str,
    weather_flags: set,
    pitcher_fip: dict | None = None,
    all_games: pd.DataFrame | None = None,
) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    used_teams = st.session_state.get(USED_TEAMS_KEY, set())
    metrics = compute_biffle_metrics(week_games, excluded_game_ids=weather_flags)
    recent_form = compute_recent_form(all_games, start_date) if all_games is not None else {}
    metrics["Form"] = metrics["Team"].map(lambda t: recent_form.get(t, "—"))
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
    _show_metrics_table(available, week_games, weather_flags, start_date, end_date, "available", pitcher_fip or {})

    if not used_rows.empty:
        with st.expander(f"Already used ({len(used_rows)} teams)"):
            _show_metrics_table(used_rows, week_games, weather_flags, start_date, end_date, "used", pitcher_fip or {})


def _show_metrics_table(
    df: pd.DataFrame,
    week_games: pd.DataFrame,
    weather_flags: set,
    start_date: str,
    end_date: str,
    key: str,
    pitcher_fip: dict,
) -> None:
    cols_to_show = ["Team", "Biffle Score", "Games", "DH", "Home", "Away",
                    "Expected Wins", "Avg Win%", "Confidence", "Form", "Actual W", "Games Played"]
    available_cols = [c for c in cols_to_show if c in df.columns]
    display = df[available_cols].copy()
    counter = st.session_state.get(f"{TABLE_COUNTER_KEY}_{key}", 0)
    tbl_key = f"tbl_{key}_{counter}"
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
        key=tbl_key,
    )
    if event.selection.rows:
        selected_team = display.iloc[event.selection.rows[0]]["Team"]
        if st.session_state.get(DIALOG_TEAM_KEY) == selected_team:
            st.session_state.pop(DIALOG_TEAM_KEY, None)
            st.session_state[f"{TABLE_COUNTER_KEY}_{key}"] = counter + 1
            st.rerun()
        else:
            st.session_state[DIALOG_TEAM_KEY] = selected_team
            _show_team_dialog(selected_team, week_games, weather_flags, pitcher_fip)

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
    pitcher_fip: dict | None = None,
) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    metrics = compute_biffle_metrics(week_games, excluded_game_ids=weather_flags)
    top_team = metrics.iloc[0]["Team"] if not metrics.empty else None
    all_teams = sorted(week_games["team_name"].dropna().unique())
    default_index = all_teams.index(top_team) if top_team in all_teams else 0

    selected_team = st.selectbox("Select team", all_teams, index=default_index)

    with st.spinner("Fetching weather forecast..."):
        rain_by_game = get_rain_probabilities(week_games)

    _render_team_game_table(selected_team, week_games, weather_flags, rain_by_game, pitcher_fip or {})

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
    pitcher_fip: dict,
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
    has_pitcher_ids = "team_pitcher_id" in team_games.columns and pitcher_fip
    has_dh = "dh" in team_games.columns

    if has_pitcher_ids:
        team_games["Our FIP"] = team_games["team_pitcher_id"].map(
            lambda pid: f"{pitcher_fip[int(pid)]:.2f}" if pd.notna(pid) and int(pid) in pitcher_fip else "—"
        )
        team_games["Opp FIP"] = team_games["opp_pitcher_id"].map(
            lambda pid: f"{pitcher_fip[int(pid)]:.2f}" if pd.notna(pid) and int(pid) in pitcher_fip else "—"
        )

    renamed = team_games.rename(columns={
        "game_date": "Date", "opponent": "Opponent",
        "team_pitcher": "Our Pitcher", "opp_pitcher": "Opp Pitcher",
        "result": "Result", "score": "Score",
    })

    shown_cols = _build_display_columns(has_pitchers, has_pitcher_ids, has_dh)
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


def _build_display_columns(has_pitchers: bool, has_pitcher_ids: bool, has_dh: bool) -> list[str]:
    if has_pitchers and has_pitcher_ids:
        cols = ["game_id", "Date", "H/A", "Opponent",
                "Our Pitcher", "Our FIP", "Opp Pitcher", "Opp FIP",
                "Win Prob", "🌧 Rain%", "Result", "Score"]
    elif has_pitchers:
        cols = ["game_id", "Date", "H/A", "Opponent",
                "Our Pitcher", "Opp Pitcher", "Win Prob", "🌧 Rain%", "Result", "Score"]
    else:
        cols = ["game_id", "Date", "H/A", "Opponent", "Win Prob", "🌧 Rain%", "Result", "Score"]
    if has_dh:
        cols = cols[:-2] + ["DH"] + cols[-2:]
    return cols + ["⛈ Weather"]


def _format_rain(pct: int | None) -> str:
    if pct is None:
        return "—"
    warning = " ⚠️" if pct >= RAIN_WARNING_THRESHOLD else ""
    return f"{pct}%{warning}"



