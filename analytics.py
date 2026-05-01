from functools import reduce
from operator import mul

import pandas as pd

NO_PROBABILITY_SENTINEL = -99


def compute_biffle_metrics(games: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for team_name, team_games in games.groupby("team_name"):
        rows.append(_build_team_row(team_name, team_games))
    return (
        pd.DataFrame(rows)
        .sort_values("Expected Wins", ascending=False)
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

    completed = team_games[team_games["result"].notna()]
    actual_wins = int((completed["result"] == "W").sum())
    games_played = len(completed)

    return {
        "Team": team_name,
        "Games": total_games,
        "Home": home_games,
        "Away": away_games,
        "Expected Wins": expected_wins,
        "Avg Win%": average_win_prob,
        "Sweep Prob": sweep_probability,
        "Probs Available": len(probabilities),
        "Actual W": actual_wins if games_played > 0 else None,
        "Games Played": games_played if games_played > 0 else None,
    }


def compute_season_summary(all_picks: list[dict], games: pd.DataFrame) -> pd.DataFrame:
    """
    Builds a season tracker row for each past pick.
    all_picks: list of {"week_label": str, "week_start": str, "team": str}
    """
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
