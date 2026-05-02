from datetime import datetime

import pandas as pd
import streamlit as st

from analytics import compute_biffle_metrics, compute_season_summary
from data_loader import load_games
from persistence import load_picks, save_picks
from sidebar import (
    USED_TEAMS_KEY,
    format_week_label,
    render_date_range,
    render_used_teams_tracker,
    render_week_picker,
)

PASSWORD_SECRET_KEY = "app_password"
SEASON_PICKS_KEY = "season_picks"


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


# ── Data helpers ──────────────────────────────────────────────────────────────

def get_week_starts(games: pd.DataFrame) -> list[str]:
    return sorted(games["week_start"].dropna().unique().tolist())


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


# ── Tabs ──────────────────────────────────────────────────────────────────────

def render_main(games: pd.DataFrame, start_date: str, end_date: str) -> None:
    st.title("Feinbermetrics")
    st.caption("Biffle Ball weekly win probability analysis")

    tab_leaderboard, tab_breakdown, tab_season = st.tabs(
        ["Weekly leaderboard", "Game breakdown", "Season tracker"]
    )

    week_games = filter_games(games, start_date, end_date)

    with tab_leaderboard:
        _render_leaderboard(week_games, start_date, end_date)
    with tab_breakdown:
        _render_game_breakdown(week_games, start_date, end_date)
    with tab_season:
        _render_season_tracker(games)


def _render_leaderboard(week_games: pd.DataFrame, start_date: str, end_date: str) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    used_teams = st.session_state.get(USED_TEAMS_KEY, set())
    metrics = compute_biffle_metrics(week_games)
    available = metrics[~metrics["Team"].isin(used_teams)].copy()
    used_rows = metrics[metrics["Team"].isin(used_teams)].copy()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Teams available", len(available))
    col2.metric("Max expected wins", f"{available['Expected Wins'].max():.1f}" if not available.empty else "—")
    col3.metric("Max games", int(available["Games"].max()) if not available.empty else "—")
    col4.metric("Date range", f"{start_date} \u2192 {end_date}")

    st.subheader("Available teams")
    st.caption(
        "**Expected Wins** = sum of FanGraphs win probabilities for each game this week. "
        "More games + higher probability = higher score. This is the primary Biffle Ball metric."
    )
    _show_metrics_table(available, start_date, end_date, "leaderboard_available")

    if not used_rows.empty:
        with st.expander(f"Already used ({len(used_rows)} teams)"):
            _show_metrics_table(used_rows, start_date, end_date, "leaderboard_used")


def _show_metrics_table(df: pd.DataFrame, start_date: str, end_date: str, key: str) -> None:
    display = df[["Team", "Games", "Home", "Away", "Expected Wins",
                  "Avg Win%", "Probs Available", "Actual W", "Games Played"]].copy()
    st.dataframe(
        display.style.format({
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


def _render_game_breakdown(week_games: pd.DataFrame, start_date: str, end_date: str) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    selected_team = st.selectbox("Select team", sorted(week_games["team_name"].dropna().unique()))
    team_games = week_games[week_games["team_name"] == selected_team].copy()
    team_games["Win Prob"] = team_games["win_probability"].apply(
        lambda p: f"{p:.1%}" if pd.notna(p) else "\u2014"
    )
    team_games["H/A"] = team_games["is_home"].map({1: "Home", 0: "Away"})

    st.dataframe(
        team_games.rename(columns={
            "game_date": "Date", "home_team": "Home", "away_team": "Away",
            "result": "Result", "score": "Score", "opponent": "Opponent",
        })[["Date", "H/A", "Opponent", "Home", "Away", "Win Prob", "Result", "Score"]],
        use_container_width=True, hide_index=True,
    )
    st.download_button(
        f"Download {selected_team} CSV",
        team_games.to_csv(index=False),
        file_name=f"{selected_team.replace(' ', '_')}_{start_date}_{end_date}.csv",
        mime="text/csv",
    )


def _render_season_tracker(games: pd.DataFrame) -> None:
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
        total_wins = int(summary["W"].sum())
        st.metric("Total wins this season", total_wins)
        st.dataframe(summary, use_container_width=True, hide_index=True)

        if st.button("Clear all picks"):
            st.session_state[SEASON_PICKS_KEY] = []
            st.rerun()
    else:
        st.info("No picks logged yet.")


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
        st.session_state["picks_initialized"] = True

    games = load_games()

    if games.empty:
        st.error("No schedule data. Run `python fetch_schedules.py` or check FanGraphs connectivity.")
        return

    start_date, end_date = render_sidebar(games)
    render_main(games, start_date, end_date)

    save_picks(
        used_teams=st.session_state.get(USED_TEAMS_KEY, set()),
        season_picks=st.session_state.get(SEASON_PICKS_KEY, []),
    )


if __name__ == "__main__":
    main()
