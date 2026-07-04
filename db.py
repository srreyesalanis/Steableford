"""
db.py — Supabase helpers para la app Stableford
"""
from supabase import create_client
import streamlit as st


import math


def round_hcp(value: float) -> int:
    """Redondea hándicap: .5 siempre sube."""
    return math.floor(value + 0.5)
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def get_authed_client():
    """Crea un cliente fresco con el token del usuario autenticado."""
    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")
    if access_token and refresh_token:
        client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        client.auth.set_session(access_token, refresh_token)
        return client
    return get_client()


def sign_in(email: str, password: str):
    """Autentica con Supabase Auth. Regresa el objeto session o lanza excepción."""
    sb = get_client()
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    return res.session


def sign_out():
    sb = get_client()
    sb.auth.sign_out()


def refresh_session(refresh_token: str):
    """Renueva el access token usando el refresh token guardado."""
    sb = get_client()
    res = sb.auth.refresh_session(refresh_token)
    return res.session


# ── Players ────────────────────────────────────────────────────────────────────

def get_players():
    sb = get_authed_client()
    res = sb.table("players").select("id, name, current_handicap").order("name").execute()
    return res.data or []


# ── Courses / Tees / Holes ─────────────────────────────────────────────────────

def get_courses():
    sb = get_authed_client()
    return (sb.table("courses").select("id, name").order("name").execute()).data or []


def get_tees(course_id: str):
    if not course_id:
        return []
    sb = get_authed_client()
    return (
        sb.table("tees")
        .select("id, name, color, rating, slope, par")
        .eq("course_id", course_id)
        .execute()
    ).data or []


def get_holes(course_id: str):
    if not course_id:
        return []
    sb = get_authed_client()
    return (
        sb.table("holes")
        .select("id, hole_number, par, handicap")
        .eq("course_id", course_id)
        .order("hole_number")
        .execute()
    ).data or []


# ── Tournaments ────────────────────────────────────────────────────────────────

def create_tournament(name: str, date: str, tee_id: str, access_code: str):
    sb = get_authed_client()
    res = (
        sb.table("tournaments")
        .insert({"name": name, "date": date, "tee_id": tee_id,
                 "format": "stableford", "access_code": access_code})
        .execute()
    )
    return res.data[0] if res.data else None


def get_tournaments():
    sb = get_authed_client()
    return (
        sb.table("tournaments")
        .select("id, name, date, access_code, tee_id")
        .order("date", desc=True)
        .execute()
    ).data or []


def get_tournament(tournament_id: str):
    sb = get_authed_client()
    res = (
        sb.table("tournaments")
        .select("id, name, date, access_code, tee_id")
        .eq("id", tournament_id)
        .single()
        .execute()
    )
    return res.data


def delete_tournament(tournament_id: str):
    """Borra el torneo y todo lo relacionado en cascada."""
    sb = get_authed_client()
    # Borrar en orden: scores → group_players → groups → guests → tournament
    sb.table("tournament_scores").delete().eq("tournament_id", tournament_id).execute()
    # Obtener grupos para borrar group_players
    groups = sb.table("groups").select("id").eq("tournament_id", tournament_id).execute().data or []
    for g in groups:
        sb.table("group_players").delete().eq("group_id", g["id"]).execute()
    sb.table("groups").delete().eq("tournament_id", tournament_id).execute()
    sb.table("guests").delete().eq("tournament_id", tournament_id).execute()
    sb.table("tournaments").delete().eq("id", tournament_id).execute()


# ── Groups ─────────────────────────────────────────────────────────────────────

def create_group(tournament_id: str, name: str, access_code: str):
    sb = get_authed_client()
    res = (
        sb.table("groups")
        .insert({"tournament_id": tournament_id, "name": name, "access_code": access_code})
        .execute()
    )
    return res.data[0] if res.data else None


def get_groups(tournament_id: str):
    sb = get_authed_client()
    return (
        sb.table("groups")
        .select("id, name, access_code")
        .eq("tournament_id", tournament_id)
        .execute()
    ).data or []


# ── Group Players ──────────────────────────────────────────────────────────────

def add_group_player(group_id: str, player_name: str, course_handicap: int,
                     player_id: str = None, guest_id: str = None):
    sb = get_authed_client()
    row = {
        "group_id": group_id,
        "player_name": player_name,
        "course_handicap": course_handicap,
        "pair_name": "",
        "pair_order": 0,
    }
    if player_id:
        row["player_id"] = player_id
    if guest_id:
        row["guest_id"] = guest_id
    res = sb.table("group_players").insert(row).execute()
    return res.data[0] if res.data else None


def get_group_players(group_id: str):
    sb = get_authed_client()
    return (
        sb.table("group_players")
        .select("id, player_id, guest_id, player_name, course_handicap")
        .eq("group_id", group_id)
        .execute()
    ).data or []


def get_all_tournament_players(tournament_id: str):
    """Devuelve todos los jugadores de todos los grupos de un torneo."""
    sb = get_authed_client()
    groups = get_groups(tournament_id)
    players = []
    for g in groups:
        gp = get_group_players(g["id"])
        for p in gp:
            p["group_name"] = g["name"]
            p["group_id"] = g["id"]
            players.append(p)
    return players


# ── Guests ─────────────────────────────────────────────────────────────────────

def create_guest(name: str, handicap_index: float, tournament_id: str, player_id: str = None):
    sb = get_authed_client()
    from datetime import date
    row = {
        "name": name,
        "handicap_index": handicap_index,
        "tournament_date": str(date.today()),
        "tournament_id": tournament_id,
    }
    if player_id:
        row["player_id"] = player_id
    res = sb.table("guests").insert(row).execute()
    return res.data[0] if res.data else None


# ── Tournament Scores ──────────────────────────────────────────────────────────

def upsert_score(tournament_id: str, hole_number: int, strokes: int,
                 net_strokes: int, group_id: str,
                 player_id: str = None, guest_id: str = None, pair_name: str = ""):
    sb = get_authed_client()
    # Buscar si ya existe
    q = (
        sb.table("tournament_scores")
        .select("id")
        .eq("tournament_id", tournament_id)
        .eq("hole_number", hole_number)
    )
    if player_id:
        q = q.eq("player_id", player_id)
    if guest_id:
        q = q.eq("guest_id", guest_id)
    existing = q.execute().data

    row = {
        "tournament_id": tournament_id,
        "hole_number": hole_number,
        "strokes": strokes,
        "net_strokes": net_strokes,
        "group_id": group_id,
        "pair_name": pair_name,
    }
    if player_id:
        row["player_id"] = player_id
    if guest_id:
        row["guest_id"] = guest_id

    if existing:
        sb.table("tournament_scores").update(row).eq("id", existing[0]["id"]).execute()
    else:
        sb.table("tournament_scores").insert(row).execute()


def get_scores(tournament_id: str):
    sb = get_authed_client()
    return (
        sb.table("tournament_scores")
        .select("player_id, guest_id, hole_number, strokes, net_strokes, group_id")
        .eq("tournament_id", tournament_id)
        .execute()
    ).data or []


def get_player_scores(tournament_id: str, player_id: str = None, guest_id: str = None):
    sb = get_authed_client()
    q = (
        sb.table("tournament_scores")
        .select("hole_number, strokes, net_strokes")
        .eq("tournament_id", tournament_id)
    )
    if player_id:
        q = q.eq("player_id", player_id)
    if guest_id:
        q = q.eq("guest_id", guest_id)
    return {r["hole_number"]: r for r in (q.execute().data or [])}
