from functools import reduce
from operator import mul

import pandas as pd

NO_PROBABILITY_SENTINEL = -99
BIFFLE_SCORE_SCALE = 7.0
RECENT_FORM_GAMES = 10


def compute_recent_form(all_games: pd.DataFrame, before_date: str) -> dict[str, str]:
    """
    Returns {team_name: "7-3 W3"} showing last-N completed games before before_date.
    Streak suffix is the current win/loss streak (e.g. "W3" or "L1").
    """
    completed = all_games[
        (all_games["result"].notna()) & (all_games["game_date"] < before_date)
    ].copy()
    completed = completed.sort_values("game_date")

    form_by_team: dict[str, str] = {}
    for team_name, team_games in completed.groupby("team_name"):
        recent = team_games.tail(RECENT_FORM_GAMES)
        wins = int((recent["result"] == "W").sum())
        losses = int((recent["result"] == "L").sum())
        streak = _compute_streak(team_games["result"].tolist())
        form_by_team[team_name] = f"{wins}-{losses} {streak}"
    return form_by_team


def _compute_streak(results: list[str]) -> str:
    if not results:
        return ""
    last = results[-1]
    count = 0
    for result in reversed(results):
        if result == last:
            count += 1
        else:
            break
    return f"{last}{count}"


def compute_biffle_metrics(
    games: pd.DataFrame,
    excluded_game_ids: set | None = None,
) -> pd.DataFrame:
    active_games = games[~games["game_id"].isin(excluded_game_ids or set())]
    rows = []
    for team_name, team_games in active_games.groupby("team_name"):
        rows.append(_build_team_row(team_name, team_games))
    return (
        pd.DataFrame(rows)
        .sort_values("Biffle Score", ascending=False)
        .reset_index(drop=True)
    )


def _build_team_row(team_name: str, team_games: pd.DataFrame) -> dict:
    total_games = len(team_games)
    home_games = int(team_games["is_home"].sum())
    away_games = total_games - home_games

    games_with_prob = team_games[team_games["win_probability"].notna()]
    probabilities = games_with_prob["win_probability"].tolist()

    expected_wins = round(sum(probabilities), 2) if probabilities else 0.0
    average_win_prob = round(sum(probabilities) / len(probabilities), 3) if probabilities else None
    sweep_probability = round(reduce(mul, probabilities, 1.0), 4) if probabilities else None
    biffle_score = round(min(expected_wins / BIFFLE_SCORE_SCALE, 1.0) * 10, 1)

    dh_games = int(team_games["dh"].sum()) if "dh" in team_games.columns else 0

    completed = team_games[team_games["result"].notna()]
    actual_wins = int((completed["result"] == "W").sum())
    games_played = len(completed)

    return {
        "Team": team_name,
        "Biffle Score": biffle_score,
        "Games": total_games,
        "DH": dh_games,
        "Home": home_games,
        "Away": away_games,
        "Expected Wins": expected_wins,
        "Avg Win%": average_win_prob,
        "Sweep Prob": sweep_probability,
        "Confidence": f"{len(probabilities)}/{total_games}",
        "Actual W": actual_wins if games_played > 0 else None,
        "Games Played": games_played if games_played > 0 else None,
    }


def compute_season_summary(all_picks: list[dict], games: pd.DataFrame) -> pd.DataFrame:
    if not all_picks:
        return pd.DataFrame()
    rows = []
    for pick in all_picks:
        team_week_games = games[
            (games["team_name"] == pick["team"])
            & (games["week_start"] == pick["week_start"])
        ]
        played = team_week_games[team_week_games["result"].notna()]
        wins = int((played["result"] == "W").sum())
        losses = int((played["result"] == "L").sum())
        remaining = len(team_week_games) - len(played)
        rows.append({
            "Week": pick["week_label"],
            "Team Picked": pick["team"],
            "W": wins,
            "L": losses,
            "Remaining": remaining,
            "Total Games": len(team_week_games),
        })
    return pd.DataFrame(rows)
