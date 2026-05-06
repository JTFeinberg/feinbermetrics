import pandas as pd
import streamlit as st

from analytics import compute_biffle_metrics, compute_recent_form
from weather import get_rain_probabilities


def render_compare_tab(
    week_games: pd.DataFrame,
    start_date: str,
    end_date: str,
    weather_flags: set,
    pitcher_fip: dict,
    all_games: pd.DataFrame,
) -> None:
    if week_games.empty:
        st.info("No games found for this date range.")
        return

    all_teams = sorted(week_games["team_name"].dropna().unique())
    if len(all_teams) < 2:
        st.info("Need at least two teams in this date range to compare.")
        return

    metrics = compute_biffle_metrics(week_games, excluded_game_ids=weather_flags)
    recent_form = compute_recent_form(all_games, start_date)
    metrics["L10"] = metrics["Team"].map(lambda t: recent_form.get(t, "—"))
    top_teams = metrics["Team"].tolist()

    col_a, col_b = st.columns(2)
    team_a = col_a.selectbox("Team A", all_teams, index=0, key="compare_a")
    default_b_index = 1 if len(all_teams) > 1 and all_teams[1] != team_a else 0
    team_b = col_b.selectbox("Team B", all_teams, index=default_b_index, key="compare_b")

    if team_a == team_b:
        st.warning("Select two different teams to compare.")
        return

    st.divider()
    _render_side_by_side_metrics(metrics, team_a, team_b)
    st.divider()

    with st.spinner("Fetching weather forecasts..."):
        rain_by_game = get_rain_probabilities(week_games)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader(team_a)
        _render_compare_game_table(team_a, week_games, weather_flags, rain_by_game, pitcher_fip)
    with col_b:
        st.subheader(team_b)
        _render_compare_game_table(team_b, week_games, weather_flags, rain_by_game, pitcher_fip)


def _render_side_by_side_metrics(metrics: pd.DataFrame, team_a: str, team_b: str) -> None:
    row_a = metrics[metrics["Team"] == team_a].iloc[0] if team_a in metrics["Team"].values else None
    row_b = metrics[metrics["Team"] == team_b].iloc[0] if team_b in metrics["Team"].values else None

    stat_cols = ["Biffle Score", "Expected Wins", "Games", "Avg Win%", "Confidence", "L10"]
    col_label, col_a, col_b = st.columns([2, 3, 3])
    col_a.markdown(f"**{team_a}**")
    col_b.markdown(f"**{team_b}**")

    for stat in stat_cols:
        col_label, col_a, col_b = st.columns([2, 3, 3])
        col_label.caption(stat)
        val_a = _format_metric(stat, row_a[stat] if row_a is not None else None)
        val_b = _format_metric(stat, row_b[stat] if row_b is not None else None)
        col_a.metric(label=stat, value=val_a, label_visibility="collapsed")
        col_b.metric(label=stat, value=val_b, label_visibility="collapsed")


def _format_metric(stat: str, value) -> str:
    if value is None:
        return "—"
    if stat == "Biffle Score":
        return f"{float(value):.1f}"
    if stat == "Expected Wins":
        return f"{float(value):.2f}"
    if stat == "Avg Win%":
        return f"{float(value):.1%}"
    return str(value)


def _render_compare_game_table(
    team_name: str,
    week_games: pd.DataFrame,
    weather_flags: set,
    rain_by_game: dict,
    pitcher_fip: dict,
) -> None:
    team_games = week_games[week_games["team_name"] == team_name].copy()
    team_games["Win Prob"] = team_games["win_probability"].apply(
        lambda p: f"{p:.1%}" if pd.notna(p) else "—"
    )
    team_games["H/A"] = team_games["is_home"].map({1: "Home", 0: "Away"})
    team_games["🌧 Rain%"] = team_games["game_id"].map(
        lambda gid: _format_rain_pct(rain_by_game.get(gid))
    )

    has_pitcher_era = "team_pitcher" in team_games.columns and bool(pitcher_fip)
    if has_pitcher_era:
        team_games["Our ERA"] = team_games["team_pitcher"].map(
            lambda name: f"{pitcher_fip[name]:.2f}" if name and name in pitcher_fip else "—"
        )

    renamed = team_games.rename(columns={
        "game_date": "Date", "opponent": "Opponent",
        "team_pitcher": "Pitcher", "result": "Result",
    })

    cols = ["Date", "H/A", "Opponent", "Pitcher"]
    if has_pitcher_era:
        cols.append("Our ERA")
    cols += ["Win Prob", "🌧 Rain%", "Result"]
    shown = [c for c in cols if c in renamed.columns]
    st.dataframe(renamed[shown], use_container_width=True, hide_index=True)


def _format_rain_pct(pct: int | None) -> str:
    if pct is None:
        return "—"
    return f"{pct}% ⚠️" if pct >= 50 else f"{pct}%"
