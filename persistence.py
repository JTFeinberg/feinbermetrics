import json
import os

PICKS_FILE = "picks.json"


def load_picks() -> dict:
    if not os.path.exists(PICKS_FILE):
        return {"used_teams": [], "season_picks": []}
    try:
        with open(PICKS_FILE) as file:
            data = json.load(file)
        return {
            "used_teams": data.get("used_teams", []),
            "season_picks": data.get("season_picks", []),
        }
    except (json.JSONDecodeError, OSError):
        return {"used_teams": [], "season_picks": []}


def save_picks(used_teams: set, season_picks: list) -> None:
    try:
        with open(PICKS_FILE, "w") as file:
            json.dump(
                {"used_teams": sorted(used_teams), "season_picks": season_picks},
                file,
                indent=2,
            )
    except OSError:
        pass
