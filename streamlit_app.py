"""
app.py — Stableford Tournament App (Streamlit + Supabase)
"""
import streamlit as st
import random
import string
from datetime import date

import db
import stableford as sf

st.set_page_config(page_title="⛳ Stableford", layout="centered")

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def ss_get(key, default=None):
    return st.session_state.get(key, default)


def ss_set(key, value):
    st.session_state[key] = value


def random_code(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTH  (Supabase Auth — email/password)
# ══════════════════════════════════════════════════════════════════════════════

def _try_restore_session():
    """Al arrancar, intenta renovar la sesión desde el refresh token guardado."""
    if ss_get("admin_logged_in"):
        return
    rt = ss_get("refresh_token")
    if not rt:
        return
    try:
        session = db.refresh_session(rt)
        if session:
            ss_set("admin_logged_in", True)
            ss_set("access_token", session.access_token)
            ss_set("refresh_token", session.refresh_token)
    except Exception:
        pass


def admin_login():
    _try_restore_session()
    if ss_get("admin_logged_in"):
        st.rerun()
        return

    st.title("🔐 Admin")
    email = st.text_input("Email")
    password = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        try:
            session = db.sign_in(email, password)
            if session:
                ss_set("admin_logged_in", True)
                ss_set("access_token", session.access_token)
                ss_set("refresh_token", session.refresh_token)
                st.rerun()
            else:
                st.error("Credenciales inválidas")
        except Exception as e:
            st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════

def admin_panel():
    st.title("⛳ Admin — Stableford")

    tab_create, tab_scores, tab_delete = st.tabs(["➕ Crear Torneo", "🎯 Capturar Scores", "🗑️ Borrar Torneo"])

    with tab_create:
        create_tournament_ui()

    with tab_scores:
        capture_scores_ui()

    with tab_delete:
        delete_tournament_ui()


# ── Crear Torneo ───────────────────────────────────────────────────────────────

def create_tournament_ui():
    st.header("Nuevo Torneo")

    courses = db.get_courses()
    if not courses:
        st.warning("No hay canchas registradas en la base de datos.")
        return

    course_map = {c["name"]: c["id"] for c in courses}
    course_name = st.selectbox("Cancha", list(course_map.keys()))
    course_id = course_map[course_name]

    tees = db.get_tees(course_id)
    if not tees:
        st.warning("Esta cancha no tiene tees configurados.")
        return

    tee_map = {f"{t['name']} ({t['color']}) — Rating {t['rating']} / Slope {t['slope']}": t for t in tees}
    tee_label = st.selectbox("Tee", list(tee_map.keys()))
    selected_tee = tee_map[tee_label]

    torneo_nombre = st.text_input("Nombre del torneo", value=f"Stableford {date.today()}")
    torneo_fecha = st.date_input("Fecha", value=date.today())

    st.subheader("Jugadores")
    all_players = db.get_players()
    player_map = {p["name"]: p for p in all_players}

    # Lista dinámica de jugadores
    if "player_rows" not in st.session_state:
        ss_set("player_rows", [{"type": "registered", "data": None}])

    rows = ss_get("player_rows")

    for i, row in enumerate(rows):
        cols = st.columns([2, 3, 2, 1])
        tipo = cols[0].selectbox(
            "Tipo", ["Registrado", "Guest"], key=f"tipo_{i}",
            index=0 if row["type"] == "registered" else 1
        )
        rows[i]["type"] = "registered" if tipo == "Registrado" else "guest"

        if rows[i]["type"] == "registered":
            name = cols[1].selectbox("Jugador", ["— Seleccionar —"] + list(player_map.keys()), key=f"pname_{i}")
            if name != "— Seleccionar —":
                p = player_map[name]
                hcp_default = float(p["current_handicap"] or 0)
                hcp = cols[2].number_input("Hándicap", value=int(round(hcp_default)), step=1, min_value=0, max_value=54, key=f"hcp_{i}")
                manual = hcp != int(round(hcp_default))
                rows[i]["data"] = {"name": name, "player_id": p["id"], "handicap_index": float(hcp), "manual_hcp": manual}
            else:
                rows[i]["data"] = None
        else:
            name = cols[1].text_input("Nombre del guest", key=f"gname_{i}")
            hcp = cols[2].number_input("Hándicap", value=0, step=1, min_value=0, max_value=54, key=f"ghcp_{i}")
            rows[i]["data"] = {"name": name, "handicap_index": float(hcp), "guest": True} if name else None

        if cols[3].button("🗑️", key=f"del_{i}") and len(rows) > 1:
            rows.pop(i)
            ss_set("player_rows", rows)
            st.rerun()

    if st.button("➕ Agregar jugador"):
        rows.append({"type": "registered", "data": None})
        ss_set("player_rows", rows)
        st.rerun()

    st.divider()

    if st.button("✅ Crear Torneo", type="primary"):
        valid = [r for r in rows if r["data"] and r["data"].get("name")]
        if not valid:
            st.error("Agrega al menos un jugador.")
            return

        # Crear torneo
        access_code = random_code()
        torneo = db.create_tournament(
            name=torneo_nombre,
            date=str(torneo_fecha),
            tee_id=selected_tee["id"],
            access_code=access_code,
        )
        if not torneo:
            st.error("Error al crear el torneo.")
            return

        # Calcular course handicap de cada jugador
        holes = db.get_holes(course_id)
        group_code = random_code()
        group = db.create_group(torneo["id"], "Grupo 1", group_code)

        for r in valid:
            d = r["data"]
            # Todos los jugadores usan el handicap index directo como course handicap
            ch = int(round(d["handicap_index"]))
            guest_id = None
            player_id = d.get("player_id")

            if d.get("guest"):
                guest = db.create_guest(d["name"], d["handicap_index"], torneo["id"])
                guest_id = guest["id"] if guest else None
                player_id = None

            db.add_group_player(
                group_id=group["id"],
                player_name=d["name"],
                course_handicap=ch,
                player_id=player_id,
                guest_id=guest_id,
            )

        ss_set("player_rows", [{"type": "registered", "data": None}])
        st.success(f"✅ Torneo **{torneo_nombre}** creado. Código de acceso: `{access_code}`")
        st.balloons()


# ── Borrar Torneo ──────────────────────────────────────────────────────────────────────────────

def delete_tournament_ui():
    st.header("🗑️ Borrar Torneo")

    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos creados.")
        return

    t_map = {f"{t['name']} ({t['date']})": t for t in tournaments}
    t_label = st.selectbox("Selecciona el torneo a borrar", list(t_map.keys()), key="delete_tournament")
    torneo = t_map[t_label]

    st.warning(f"⚠️ Esto borrará **{torneo['name']}** y todos sus scores, grupos y jugadores. Esta acción no se puede deshacer.")

    confirm = st.checkbox("Confirmo que quiero borrar este torneo", key="delete_confirm")

    if st.button("🗑️ Borrar Torneo", type="primary", disabled=not confirm):
        db.delete_tournament(torneo["id"])
        st.success(f"✅ Torneo **{torneo['name']}** borrado.")
        st.rerun()


# ── Capturar Scores ────────────────────────────────────────────────────────────

def capture_scores_ui():
    st.header("Capturar Scores")

    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos creados.")
        return

    t_map = {f"{t['name']} ({t['date']})": t for t in tournaments}
    t_label = st.selectbox("Torneo", list(t_map.keys()), key="score_tournament")
    torneo = t_map[t_label]

    # Tee info
    tee_id = torneo.get("tee_id")
    if not tee_id:
        st.warning("Este torneo no tiene tee asignado.")
        return

    sb = db.get_authed_client()
    tee_res = sb.table("tees").select("*").eq("id", tee_id).execute()
    if not tee_res.data:
        st.warning("No se encontró el tee del torneo.")
        return
    tee = tee_res.data[0]

    course_id = tee.get("course_id")
    if not course_id:
        st.warning("El tee no tiene cancha asignada.")
        return

    course_res = sb.table("courses").select("id, name").eq("id", course_id).execute()
    course = course_res.data[0] if course_res.data else {}

    holes = db.get_holes(course.get("id", ""))
    if not holes:
        st.warning("No hay hoyos configurados para esta cancha.")
        return

    players = db.get_all_tournament_players(torneo["id"])
    if not players:
        st.warning("No hay jugadores en este torneo.")
        return

    # Selector de jugador
    p_map = {p["player_name"]: p for p in players}
    p_name = st.selectbox("Jugador", list(p_map.keys()), key="score_player")
    player = p_map[p_name]

    course_hcp = player["course_handicap"]
    st.caption(f"Course Handicap: **{course_hcp}**")

    # Scores existentes
    existing = db.get_player_scores(
        torneo["id"],
        player_id=player.get("player_id"),
        guest_id=player.get("guest_id"),
    )

    st.divider()

    for hole in holes:
        hnum = hole["hole_number"]
        par = hole["par"]
        hh = hole["handicap"]  # hole handicap (dificultad)
        received = sf.strokes_received(course_hcp, hh)

        saved = existing.get(hnum, {})
        default_strokes = saved.get("strokes", par)

        with st.expander(f"Hoyo {hnum} — Par {par} | HCP {hh} | Ventaja: +{received}", expanded=hnum == 1):
            gross = st.number_input(
                "Golpes brutos", min_value=1, max_value=15,
                value=default_strokes, key=f"gross_{hnum}"
            )
            calc = sf.calc_hole(gross, par, course_hcp, hh)
            col1, col2, col3 = st.columns(3)
            col1.metric("Net", calc["net"])
            col2.metric("Puntos", calc["points"])
            col3.metric("vs Par", f"{calc['net'] - par:+d}")

            if st.button(f"💾 Guardar Hoyo {hnum}", key=f"save_{hnum}"):
                db.upsert_score(
                    tournament_id=torneo["id"],
                    hole_number=hnum,
                    strokes=gross,
                    net_strokes=calc["net"],
                    group_id=player["group_id"],
                    player_id=player.get("player_id"),
                    guest_id=player.get("guest_id"),
                )
                st.success(f"✅ Hoyo {hnum} guardado — {calc['points']} pts")


# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD (vista pública)
# ══════════════════════════════════════════════════════════════════════════════

def leaderboard_ui():
    st.title("⛳ Leaderboard — Stableford")

    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos disponibles.")
        return

    t_map = {f"{t['name']} ({t['date']})": t for t in tournaments}
    t_label = st.selectbox("Torneo", list(t_map.keys()))
    torneo = t_map[t_label]

    players = db.get_all_tournament_players(torneo["id"])
    scores_raw = db.get_scores(torneo["id"])

    # Agrupar puntos por jugador
    from collections import defaultdict
    pts_by_player = defaultdict(int)
    holes_by_player = defaultdict(int)

    # Necesitamos course_hcp por jugador
    hcp_map = {p["player_id"] or p["guest_id"]: p["course_handicap"] for p in players}

    sb = db.get_authed_client()
    tee_id = torneo.get("tee_id")
    tee = {}
    course = {}
    if tee_id:
        tee_res = sb.table("tees").select("*").eq("id", tee_id).execute()
        tee = tee_res.data[0] if tee_res.data else {}
    course_id = tee.get("course_id")
    if course_id:
        course_res = sb.table("courses").select("id").eq("id", course_id).execute()
        course = course_res.data[0] if course_res.data else {}
    holes = {h["hole_number"]: h for h in db.get_holes(course.get("id", ""))}

    for s in scores_raw:
        pid = s.get("player_id") or s.get("guest_id")
        hole = holes.get(s["hole_number"])
        if not hole or not pid:
            continue
        ch = hcp_map.get(pid, 0)
        calc = sf.calc_hole(s["strokes"], hole["par"], ch, hole["handicap"])
        pts_by_player[pid] += calc["points"]
        holes_by_player[pid] += 1

    # Construir tabla
    rows = []
    for p in players:
        pid = p.get("player_id") or p.get("guest_id")
        rows.append({
            "Jugador": p["player_name"],
            "Hoyos": holes_by_player.get(pid, 0),
            "Puntos": pts_by_player.get(pid, 0),
        })

    rows.sort(key=lambda x: -x["Puntos"])

    for i, r in enumerate(rows):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
        st.markdown(
            f"**{medal} {r['Jugador']}** — {r['Puntos']} pts &nbsp;&nbsp; _(Hoyos: {r['Hoyos']})_"
        )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    st.sidebar.title("⛳ Stableford")
    vista = st.sidebar.radio("Vista", ["🏆 Leaderboard", "🔐 Admin"])

    if vista == "🔐 Admin":
        if not ss_get("admin_logged_in"):
            admin_login()
        else:
            if st.sidebar.button("Cerrar sesión"):
                db.sign_out()
                ss_set("admin_logged_in", False)
                ss_set("access_token", None)
                ss_set("refresh_token", None)
                st.rerun()
            admin_panel()
    else:
        leaderboard_ui()


if __name__ == "__main__":
    main()

