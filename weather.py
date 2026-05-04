import requests
import streamlit as st

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
RAIN_WARNING_THRESHOLD = 50

MLB_STADIUM_COORDINATES: dict[str, tuple[float, float]] = {
    "Angels":        (33.8003, -117.8827),
    "Astros":        (29.7572,  -95.3555),
    "Athletics":     (37.7516, -122.2005),
    "Blue Jays":     (43.6414,  -79.3894),
    "Braves":        (33.8908,  -84.4677),
    "Brewers":       (43.0280,  -87.9712),
    "Cardinals":     (38.6226,  -90.1928),
    "Cubs":          (41.9484,  -87.6553),
    "Diamondbacks":  (33.4453, -112.0668),
    "Dodgers":       (34.0739, -118.2400),
    "Giants":        (37.7786, -122.3893),
    "Guardians":     (41.4962,  -81.6852),
    "Mariners":      (47.5914, -122.3325),
    "Marlins":       (25.7781,  -80.2197),
    "Mets":          (40.7571,  -73.8458),
    "Nationals":     (38.8730,  -77.0074),
    "Orioles":       (39.2838,  -76.6217),
    "Padres":        (32.7076, -117.1570),
    "Phillies":      (39.9061,  -75.1665),
    "Pirates":       (40.4469,  -80.0057),
    "Rangers":       (32.7473,  -97.0845),
    "Rays":          (27.7682,  -82.6534),
    "Red Sox":       (42.3467,  -71.0972),
    "Reds":          (39.0979,  -84.5082),
    "Rockies":       (39.7559, -104.9942),
    "Royals":        (39.0517,  -94.4803),
    "Tigers":        (42.3390,  -83.0485),
    "Twins":         (44.9817,  -93.2776),
    "White Sox":     (41.8299,  -87.6338),
    "Yankees":       (40.8296,  -73.9262),
}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fetch_daily_rain(lat: float, lon: float, start_date: str, end_date: str) -> dict[str, int]:
    try:
        response = requests.get(OPEN_METEO_URL, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "precipitation_probability_max",
            "timezone": "auto",
            "start_date": start_date,
            "end_date": end_date,
        }, timeout=5)
        response.raise_for_status()
        data = response.json().get("daily", {})
        dates = data.get("time", [])
        probs = data.get("precipitation_probability_max", [])
        return dict(zip(dates, probs))
    except (requests.RequestException, KeyError, ValueError):
        return {}


def get_rain_probabilities(week_games) -> dict[str, int | None]:
    """
    Returns {game_id: rain_pct} for every game in week_games.
    Uses the home team's stadium coordinates since that determines weather.
    Batches all dates per stadium into a single API call.
    """
    from collections import defaultdict
    stadium_dates: dict[str, list] = defaultdict(list)

    for _, row in week_games.iterrows():
        home_team = row.get("home_team", "")
        if home_team in MLB_STADIUM_COORDINATES:
            stadium_dates[home_team].append((row["game_id"], row["game_date"]))

    rain_by_game: dict[str, int | None] = {row["game_id"]: None for _, row in week_games.iterrows()}

    for home_team, game_list in stadium_dates.items():
        coords = MLB_STADIUM_COORDINATES[home_team]
        all_dates = [g[1] for g in game_list]
        forecasts = _fetch_daily_rain(coords[0], coords[1], min(all_dates), max(all_dates))
        for game_id, game_date in game_list:
            rain_by_game[game_id] = forecasts.get(game_date)

    return rain_by_game
