import hashlib
import json

import streamlit as st
from supabase import Client, create_client

PICKS_SAVE_HASH_KEY = "_picks_save_hash"
WEATHER_SAVE_HASH_KEY = "_weather_save_hash"


@st.cache_resource
def _get_client() -> Client:
    return create_client(
        st.secrets["supabase_url"],
        st.secrets["supabase_anon_key"],
    )


def load_picks() -> dict:
    client = _get_client()
    used_response = client.table("used_teams").select("team_name").execute()
    picks_response = (
        client.table("season_picks")
        .select("week_start, week_label, team")
        .order("week_start")
        .execute()
    )
    return {
        "used_teams": [row["team_name"] for row in used_response.data],
        "season_picks": [
            {"week_start": r["week_start"], "week_label": r["week_label"], "team": r["team"]}
            for r in picks_response.data
        ],
    }


def save_picks(used_teams: set, season_picks: list) -> None:
    current_hash = _compute_hash({"used_teams": sorted(used_teams), "season_picks": season_picks})
    if st.session_state.get(PICKS_SAVE_HASH_KEY) == current_hash:
        return
    client = _get_client()
    client.table("used_teams").delete().neq("team_name", "").execute()
    if used_teams:
        client.table("used_teams").insert(
            [{"team_name": t} for t in sorted(used_teams)]
        ).execute()
    client.table("season_picks").delete().neq("week_start", "").execute()
    if season_picks:
        client.table("season_picks").insert(
            [{"week_start": p["week_start"], "week_label": p["week_label"], "team": p["team"]}
             for p in season_picks]
        ).execute()
    st.session_state[PICKS_SAVE_HASH_KEY] = current_hash


def load_weather_flags() -> set:
    client = _get_client()
    response = client.table("weather_flags").select("game_id").execute()
    return {row["game_id"] for row in response.data}


def save_weather_flags(game_ids: set) -> None:
    current_hash = _compute_hash({"game_ids": sorted(game_ids)})
    if st.session_state.get(WEATHER_SAVE_HASH_KEY) == current_hash:
        return
    client = _get_client()
    client.table("weather_flags").delete().neq("game_id", "").execute()
    if game_ids:
        client.table("weather_flags").insert(
            [{"game_id": g} for g in sorted(game_ids)]
        ).execute()
    st.session_state[WEATHER_SAVE_HASH_KEY] = current_hash


def _compute_hash(state: dict) -> str:
    return hashlib.md5(json.dumps(state, sort_keys=True).encode()).hexdigest()
