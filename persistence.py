import hashlib
import json

import requests
import streamlit as st

PICKS_SAVE_HASH_KEY = "_picks_save_hash"
WEATHER_SAVE_HASH_KEY = "_weather_save_hash"


def _headers() -> dict:
    key = st.secrets["supabase_anon_key"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _url(table: str, query: str = "") -> str:
    base = st.secrets["supabase_url"].rstrip("/")
    return f"{base}/rest/v1/{table}{query}"


def _select(table: str, columns: str = "*", order: str = "") -> list:
    params = f"?select={columns}" + (f"&order={order}" if order else "")
    response = requests.get(_url(table, params), headers=_headers(), timeout=10)
    if not response.ok:
        st.error(f"Supabase error on table `{table}` — HTTP {response.status_code}")
        st.code(response.text[:500])
        st.stop()
    return response.json()


def _delete_all(table: str, primary_key: str) -> None:
    requests.delete(_url(table, f"?{primary_key}=not.is.null"), headers=_headers(), timeout=10)


def _insert(table: str, rows: list) -> None:
    if not rows:
        return
    requests.post(_url(table), headers=_headers(), json=rows, timeout=10).raise_for_status()


def load_picks() -> dict:
    used = _select("used_teams", columns="team_name")
    picks = _select("season_picks", columns="week_start,week_label,team", order="week_start")
    return {
        "used_teams": [row["team_name"] for row in used],
        "season_picks": [
            {"week_start": r["week_start"], "week_label": r["week_label"], "team": r["team"]}
            for r in picks
        ],
    }


def save_picks(used_teams: set, season_picks: list) -> None:
    current_hash = _hash({"used_teams": sorted(used_teams), "season_picks": season_picks})
    if st.session_state.get(PICKS_SAVE_HASH_KEY) == current_hash:
        return
    _delete_all("used_teams", "team_name")
    _insert("used_teams", [{"team_name": t} for t in sorted(used_teams)])
    _delete_all("season_picks", "week_start")
    _insert("season_picks", [
        {"week_start": p["week_start"], "week_label": p["week_label"], "team": p["team"]}
        for p in season_picks
    ])
    st.session_state[PICKS_SAVE_HASH_KEY] = current_hash


def load_weather_flags() -> set:
    rows = _select("weather_flags", columns="game_id")
    return {row["game_id"] for row in rows}


def save_weather_flags(game_ids: set) -> None:
    current_hash = _hash({"game_ids": sorted(game_ids)})
    if st.session_state.get(WEATHER_SAVE_HASH_KEY) == current_hash:
        return
    _delete_all("weather_flags", "game_id")
    _insert("weather_flags", [{"game_id": g} for g in sorted(game_ids)])
    st.session_state[WEATHER_SAVE_HASH_KEY] = current_hash


def _hash(state: dict) -> str:
    return hashlib.md5(json.dumps(state, sort_keys=True).encode()).hexdigest()
