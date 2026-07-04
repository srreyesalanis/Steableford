"""
streamlit_app.py — Stableford Tournament App (Streamlit + Supabase)
"""
import streamlit as st
import random
import string
from datetime import date
from collections import defaultdict

import db
import stableford as sf

st.set_page_config(page_title="⛳ Stableford", layout="centered")

st.markdown("""
<style>
h1 { font-size: 1.4rem !important; }
h2 { font-size: 1.1rem !important; }
h3 { font-size: 1rem !important; }
div[data-testid="stNumberInput"] input {
    font-size: 1.2rem !important;
    height: 2.5rem !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
    width: 100%;
    font-size: 1.1rem;
    padding: 0.6rem;
}
section[data-testid="stSidebar"] { min-width: 200px !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def ss_get(key, default=None):
    return st.session_state.get(key, default)

def ss_set(key, value):
    st.session_state[key] = value

def random_numeric_code(n=6):
    return "".join(random.choices(string.digits, k=n))

def random_code(n=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTH
# ══════════════════════════════════════════════════════════════════════════════

def _try_restore_session():
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
    tab_create, tab_scores, tab_codes, tab_delete = st.tabs(["➕ Crear Torneo", "🎯 Capturar Scores", "🔑 Ver Códigos", "🗑️ Borrar Torneo"])
    with tab_create:
        create_tournament_ui()
    with tab_scores:
        capture_scores_ui(admin=True)
    with tab_codes:
        view_codes_ui()
    with tab_delete:
        delete_tournament_ui()

# ── Crear Torneo ───────────────────────────────────────────────────────────────

def create_tournament_ui():
    st.header("Nuevo Torneo")

    courses = db.get_courses()
    if not courses:
        st.warning("No hay canchas registradas.")
        return

    course_map = {c["name"]: c["id"] for c in courses}
    course_name = st.selectbox("Cancha", list(course_map.keys()))
    course_id = course_map[course_name]

    tees = db.get_tees(course_id)
    if not tees:
        st.warning("Esta cancha no tiene tees.")
        return

    tee_map = {f"{t['name']} ({t['color']}) — Rating {t['rating']} / Slope {t['slope']}": t for t in tees}
    tee_label = st.selectbox("Tee", list(tee_map.keys()))
    selected_tee = tee_map[tee_label]

    torneo_nombre = st.text_input("Nombre del torneo", value=f"Stableford {date.today()}")
    torneo_fecha = st.date_input("Fecha", value=date.today())

    # ── Número de grupos ──
    n_grupos = st.number_input("Número de grupos", min_value=1, max_value=20, value=ss_get("n_grupos", 1), step=1)
    ss_set("n_grupos", n_grupos)

    all_players = db.get_players()
    player_map = {p["name"]: p for p in all_players}

    # Inicializar estructura de grupos en session_state
    if "grupos" not in st.session_state or len(ss_get("grupos")) != n_grupos:
        ss_set("grupos", [
            {"name": f"Grupo {i+1}", "rows": [{"type": "registered", "data": None}]}
            for i in range(n_grupos)
        ])

    grupos = ss_get("grupos")

    for gi in range(n_grupos):
        g = grupos[gi]
        st.divider()
        st.subheader(f"🏌️ Grupo {gi+1}")
        g["name"] = st.text_input("Nombre del grupo", value=g["name"], key=f"gname_{gi}")

        rows = g["rows"]
        for i, row in enumerate(rows):
            cols = st.columns([2, 3, 2, 1])
            tipo = cols[0].selectbox("Tipo", ["Registrado", "Guest"],
                                     index=0 if row["type"] == "registered" else 1,
                                     key=f"tipo_{gi}_{i}")
            rows[i]["type"] = "registered" if tipo == "Registrado" else "guest"

            if rows[i]["type"] == "registered":
                name = cols[1].selectbox("Jugador", ["— Seleccionar —"] + list(player_map.keys()), key=f"pname_{gi}_{i}")
                if name != "— Seleccionar —":
                    p = player_map[name]
                    hcp_default = db.round_hcp(float(p["current_handicap"] or 0))
                    hcp = cols[2].number_input("HCP", value=hcp_default, step=1, min_value=0, max_value=54, key=f"hcp_{gi}_{i}")
                    rows[i]["data"] = {"name": name, "player_id": p["id"], "handicap_index": float(hcp)}
                else:
                    rows[i]["data"] = None
            else:
                name = cols[1].text_input("Nombre del guest", key=f"gname_p_{gi}_{i}")
                hcp = cols[2].number_input("HCP", value=0, step=1, min_value=0, max_value=54, key=f"ghcp_{gi}_{i}")
                rows[i]["data"] = {"name": name, "handicap_index": float(hcp), "guest": True} if name else None

            if cols[3].button("🗑️", key=f"del_{gi}_{i}") and len(rows) > 1:
                rows.pop(i)
                ss_set("grupos", grupos)
                st.rerun()

        if st.button(f"➕ Jugador en Grupo {gi+1}", key=f"add_player_{gi}"):
            rows.append({"type": "registered", "data": None})
            ss_set("grupos", grupos)
            st.rerun()

    st.divider()

    if st.button("✅ Crear Torneo", type="primary"):
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

        codigos = []
        for gi, g in enumerate(grupos):
            valid = [r for r in g["rows"] if r["data"] and r["data"].get("name")]
            if not valid:
                continue

            group_code = random_numeric_code(6)
            group = db.create_group(torneo["id"], g["name"], group_code)
            codigos.append({"nombre": g["name"], "codigo": group_code})

            for r in valid:
                d = r["data"]
                guest_id = None
                player_id = d.get("player_id")

                # Calcular Course Handicap real: HI × (Slope/113) + (CR - Par)
                ch = sf.course_handicap(
                    d["handicap_index"],
                    selected_tee["slope"],
                    float(selected_tee["rating"]),
                    selected_tee["par"],
                )

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

        ss_set("grupos", None)
        st.session_state.pop("grupos", None)

        st.success(f"✅ Torneo **{torneo_nombre}** creado con {len(codigos)} grupo(s)")
        st.subheader("🔑 Códigos de grupo")
        for c in codigos:
            st.markdown(
                f"<div style='background:#e8f5e9;border-radius:8px;padding:10px 16px;margin-bottom:8px;font-size:1rem'>"
                f"<b>{c['nombre']}</b> — código: "
                f"<span style='font-size:1.4rem;font-weight:bold;letter-spacing:4px'>{c['codigo']}</span>"
                f"</div>",
                unsafe_allow_html=True
            )
        st.balloons()

# ── Ver Códigos ───────────────────────────────────────────────────────────────

def view_codes_ui():
    st.header("🔑 Códigos de Grupo")
    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos creados.")
        return

    t_map = {t['name']: t for t in tournaments}
    t_label = st.selectbox("Torneo", list(t_map.keys()), key="codes_tournament")
    torneo = t_map[t_label]

    grupos = db.get_groups(torneo["id"])
    if not grupos:
        st.warning("Este torneo no tiene grupos.")
        return

    for g in grupos:
        players = db.get_group_players(g["id"])
        names = ", ".join(p["player_name"] for p in players) or "Sin jugadores"
        st.markdown(
            f"<div style='background:#e8f5e9;border-radius:10px;padding:12px 16px;margin-bottom:10px'>"
            f"<b>{g['name']}</b><br>"
            f"<span style='font-size:2rem;font-weight:bold;letter-spacing:6px'>{g['access_code']}</span><br>"
            f"<span style='color:#555;font-size:0.85rem'>{names}</span>"
            f"</div>",
            unsafe_allow_html=True
        )



def delete_tournament_ui():
    st.header("🗑️ Borrar Torneo")
    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos creados.")
        return

    t_map = {t['name']: t for t in tournaments}
    t_label = st.selectbox("Torneo a borrar", list(t_map.keys()), key="delete_tournament")
    torneo = t_map[t_label]

    st.warning(f"⚠️ Borrará **{torneo['name']}** y todos sus datos.")
    confirm = st.checkbox("Confirmo", key="delete_confirm")

    if st.button("🗑️ Borrar", type="primary", disabled=not confirm):
        db.delete_tournament(torneo["id"])
        st.success(f"✅ Torneo **{torneo['name']}** borrado.")
        st.rerun()

# ── Capturar Scores (admin ve todos; líder ve solo su grupo) ───────────────────

def capture_scores_ui(admin=False, group=None, torneo=None):
    """
    admin=True  → el admin selecciona torneo y grupo
    admin=False → group y torneo ya vienen del login por código
    """
    if admin:
        st.header("Capturar Scores")
        tournaments = db.get_tournaments()
        if not tournaments:
            st.info("No hay torneos creados.")
            return
        t_map = {t['name']: t for t in tournaments}
        t_label = st.selectbox("Torneo", list(t_map.keys()), key="score_tournament")
        torneo = t_map[t_label]

        grupos = db.get_groups(torneo["id"])
        if not grupos:
            st.warning("Este torneo no tiene grupos.")
            return
        g_map = {g["name"]: g for g in grupos}
        g_label = st.selectbox("Grupo", list(g_map.keys()), key="score_group")
        group = g_map[g_label]

    _capture_group_scores(torneo, group)


def _capture_group_scores(torneo, group):
    tee_id = torneo.get("tee_id")
    if not tee_id:
        st.warning("El torneo no tiene tee asignado.")
        return

    sb = db.get_authed_client()
    tee_res = sb.table("tees").select("*").eq("id", tee_id).execute()
    if not tee_res.data:
        st.warning("No se encontró el tee.")
        return
    tee = tee_res.data[0]
    course_id = tee.get("course_id")
    if not course_id:
        st.warning("El tee no tiene cancha.")
        return

    course_res = sb.table("courses").select("id").eq("id", course_id).execute()
    course = course_res.data[0] if course_res.data else {}

    holes = db.get_holes(course.get("id", ""))
    if not holes:
        st.warning("No hay hoyos configurados.")
        return

    players = db.get_group_players(group["id"])
    if not players:
        st.warning("No hay jugadores en este grupo.")
        return

    saved_holes = {s["hole_number"] for s in db.get_scores(torneo["id"]) if s.get("group_id") == group["id"]}

    hole_list = [
        f"{'✅ ' if h['hole_number'] in saved_holes else ''}Hoyo {h['hole_number']} — Par {h['par']} | HCP {h['handicap']}"
        for h in holes
    ]
    hole_options = {label: hole for label, hole in zip(hole_list, holes)}

    default_idx = ss_get(f"hole_idx_{group['id']}", 0)
    hole_label = st.selectbox("Hoyo", hole_list, index=default_idx, key=f"hole_{group['id']}")
    hole = hole_options[hole_label]
    hnum = hole["hole_number"]
    par = hole["par"]
    hh = hole["handicap"]

    st.divider()

    cache_key = f"scores_{torneo['id']}_{group['id']}_{hnum}"
    if cache_key not in st.session_state:
        existing_all = {}
        for p in players:
            scores = db.get_player_scores(torneo["id"], player_id=p.get("player_id"), guest_id=p.get("guest_id"))
            existing_all[p["id"]] = scores
        ss_set(cache_key, existing_all)
    existing_all = ss_get(cache_key)

    COLORS = ["#e3f2fd", "#f3e5f5", "#e8f5e9", "#fff8e1", "#fce4ec", "#e0f7fa", "#f1f8e9", "#ede7f6"]

    with st.form(key=f"form_{torneo['id']}_{group['id']}_{hnum}"):
        scores_input = {}
        for idx, player in enumerate(players):
            course_hcp = player["course_handicap"]
            received = sf.strokes_received(course_hcp, hh)
            existing = existing_all.get(player["id"], {})
            saved = existing.get(hnum, {})
            default_strokes = saved.get("strokes", par)

            color = COLORS[idx % len(COLORS)]
            ventaja = f" | Ventaja: {received}" if received > 0 else ""
            prev_calc = sf.calc_hole(default_strokes, par, course_hcp, hh)

            st.markdown(
                f"<div style='background:{color};border-radius:10px 10px 0 0;padding:8px 14px 6px 14px'>"
                f"<b>{player['player_name']}</b> "
                f"<span style='color:#555;font-size:0.85rem'>HCP {course_hcp}{ventaja}</span>"
                f"&nbsp;&nbsp;<span style='font-size:0.85rem'>Net: <b>{prev_calc['net']}</b> &nbsp; Pts: <b>{prev_calc['points']}</b></span>"
                f"</div>",
                unsafe_allow_html=True
            )
            gross = st.number_input(
                "Golpes", min_value=1, max_value=15,
                value=default_strokes, key=f"gross_{hnum}_{group['id']}_{player['id']}",
                label_visibility="collapsed"
            )
            calc = sf.calc_hole(gross, par, course_hcp, hh)
            st.markdown(
                f"<div style='background:{color};border-radius:0 0 10px 10px;height:6px;margin-top:-8px;margin-bottom:10px'></div>",
                unsafe_allow_html=True
            )
            scores_input[player["id"]] = {"player": player, "gross": gross, "calc": calc}

        submitted = st.form_submit_button(f"💾 Guardar Hoyo {hnum}", type="primary", use_container_width=True)

    if submitted:
        for pid, s in scores_input.items():
            p = s["player"]
            db.upsert_score(
                tournament_id=torneo["id"],
                hole_number=hnum,
                strokes=s["gross"],
                net_strokes=s["calc"]["net"],
                group_id=group["id"],
                player_id=p.get("player_id"),
                guest_id=p.get("guest_id"),
            )
        st.session_state.pop(cache_key, None)
        if hnum >= len(holes):
            ss_set(f"hole_idx_{group['id']}", len(holes) - 1)
            st.success("🏁 ¡Ronda completa!")
            st.balloons()
        else:
            ss_set(f"hole_idx_{group['id']}", hnum)
            st.success(f"✅ Hoyo {hnum} guardado — siguiente: Hoyo {hnum + 1}")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════

def leaderboard_ui():
    st.title("⛳ Leaderboard — Stableford")

    tournaments = db.get_tournaments()
    if not tournaments:
        st.info("No hay torneos disponibles.")
        return

    t_map = {t['name']: t for t in tournaments}
    t_label = st.selectbox("Torneo", list(t_map.keys()))
    torneo = t_map[t_label]

    players = db.get_all_tournament_players(torneo["id"])
    scores_raw = db.get_scores(torneo["id"])

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
    holes_list = db.get_holes(course.get("id", ""))
    holes = {h["hole_number"]: h for h in holes_list}
    hole_nums = sorted(holes.keys())

    pts_by_player = defaultdict(int)
    holes_by_player = defaultdict(int)
    detail = defaultdict(dict)

    for s in scores_raw:
        pid = s.get("player_id") or s.get("guest_id")
        hole = holes.get(s["hole_number"])
        if not hole or not pid:
            continue
        ch = hcp_map.get(pid, 0)
        calc = sf.calc_hole(s["strokes"], hole["par"], ch, hole["handicap"])
        pts_by_player[pid] += calc["points"]
        holes_by_player[pid] += 1
        detail[pid][s["hole_number"]] = {"strokes": s["strokes"], "points": calc["points"]}

    ranked = []
    for p in players:
        pid = p.get("player_id") or p.get("guest_id")
        ranked.append({"pid": pid, "name": p["player_name"], "pts": pts_by_player.get(pid, 0), "hoyos": holes_by_player.get(pid, 0)})
    ranked.sort(key=lambda x: -x["pts"])

    # ── Hoyo común: el más avanzado que TODOS los jugadores tienen ────────────
    all_pids = [p.get("player_id") or p.get("guest_id") for p in players]
    if all_pids and all(pid in detail for pid in all_pids):
        common_holes = sorted(
            set.intersection(*[set(detail[pid].keys()) for pid in all_pids])
        )
    else:
        common_holes = []
    last_common = max(common_holes) if common_holes else 0

    # Front común: hoyos 1-9 que todos tienen; Back: hoyos 10-18 que todos tienen
    common_front = [h for h in common_holes if h <= 9]
    common_back  = [h for h in common_holes if h > 9]

    front_pts_map = defaultdict(int)
    back_pts_map  = defaultdict(int)
    total_common_map = defaultdict(int)
    for pid_w in all_pids:
        for hnum in common_front:
            front_pts_map[pid_w] += detail[pid_w].get(hnum, {}).get("points", 0)
        for hnum in common_back:
            back_pts_map[pid_w] += detail[pid_w].get(hnum, {}).get("points", 0)
        total_common_map[pid_w] = front_pts_map[pid_w] + back_pts_map[pid_w]

    common_label = f"(hasta H{last_common})" if last_common else "(sin datos)"

    pid_to_name = {(p.get("player_id") or p.get("guest_id")): p["player_name"] for p in players}

    def _winner_card(label, pts_map, icon, subtitle=""):
        if not pts_map:
            return
        best_pts = max(pts_map.values())
        winners = [pid_to_name.get(p, "?") for p, v in pts_map.items() if v == best_pts]
        names_str = " / ".join(winners)
        tie_label = " 🤝 Empate" if len(winners) > 1 else ""
        sub_html = f"<br><span style='font-size:0.72rem;color:#aaa'>{subtitle}</span>" if subtitle else ""
        st.markdown(
            f"<div style='background:#fff8e1;border-left:4px solid #ffc107;border-radius:8px;"
            f"padding:10px 14px;margin-bottom:8px'>"
            f"<span style='font-size:0.8rem;color:#888'>{icon} {label}{tie_label}</span>{sub_html}<br>"
            f"<b style='font-size:1.1rem'>{names_str}</b>"
            f"<span style='color:#f57c00;margin-left:8px;font-weight:bold'>{best_pts} pts</span>"
            f"</div>",
            unsafe_allow_html=True
        )

    if ranked:
        st.markdown(f"### 🏆 Ganadores {common_label}")
        col1, col2, col3 = st.columns(3)
        with col1:
            _winner_card("Front 9", dict(front_pts_map), "🌅", common_label)
        with col2:
            _winner_card("Back 9", dict(back_pts_map), "🌆", common_label)
        with col3:
            _winner_card("Torneo", dict(total_common_map), "🎖️", common_label)

    if hole_nums and any(detail.values()):
        st.subheader("📊 Detalle por hoyo")

        header = "<tr><th style='text-align:left;padding:4px 8px'>Jugador</th>"
        for h in hole_nums:
            ph = holes[h]["par"]
            header += f"<th style='text-align:center;padding:4px 6px'>H{h}<br><span style='font-size:0.7rem;color:#888'>P{ph}</span></th>"
            if h == 9:
                header += "<th style='text-align:center;padding:4px 6px;background:#e3f2fd'><b>F9</b></th>"
            elif h == 18:
                header += "<th style='text-align:center;padding:4px 6px;background:#e3f2fd'><b>B9</b></th>"
        header += "<th style='text-align:center;padding:4px 8px;background:#bbdefb'><b>Total</b></th></tr>"

        body = ""
        for r in ranked:
            pid = r["pid"]
            body += f"<tr><td style='padding:4px 8px;white-space:nowrap'><b>{r['name']}</b></td>"
            front_pts = 0; back_pts = 0
            front_str = 0; back_str = 0
            total_str = 0
            for h in hole_nums:
                d = detail[pid].get(h)
                if d:
                    pts = d["points"]
                    strokes = d["strokes"]
                    bg = "#c8e6c9" if pts >= 3 else "#fff9c4" if pts == 2 else "#ffcdd2" if pts == 1 else "#ef9a9a"
                    body += f"<td style='text-align:center;background:{bg};padding:4px 6px'>{strokes}<br><span style='font-size:0.75rem;font-weight:bold'>{pts}p</span></td>"
                    total_str += strokes
                    if h <= 9:
                        front_pts += pts; front_str += strokes
                    else:
                        back_pts += pts; back_str += strokes
                else:
                    body += "<td style='text-align:center;color:#ccc;padding:4px 6px'>—</td>"
                if h == 9:
                    body += f"<td style='text-align:center;background:#e3f2fd;padding:4px 6px;font-weight:bold'>{front_str}<br><span style='font-size:0.75rem;color:#1565c0'>{front_pts}p</span></td>"
                elif h == 18:
                    body += f"<td style='text-align:center;background:#e3f2fd;padding:4px 6px;font-weight:bold'>{back_str}<br><span style='font-size:0.75rem;color:#1565c0'>{back_pts}p</span></td>"
            body += f"<td style='text-align:center;font-weight:bold;padding:4px 8px;background:#bbdefb'>{total_str}<br><span style='font-size:0.75rem;color:#0d47a1'>{r['pts']}p</span></td></tr>"

        st.markdown(
            f"<div style='overflow-x:auto'><table style='border-collapse:collapse;width:100%;font-size:0.85rem'>"
            f"{header}{body}</table></div>",
            unsafe_allow_html=True
        )

# ══════════════════════════════════════════════════════════════════════════════
# VISTA LÍDER DE GRUPO (acceso por código)
# ══════════════════════════════════════════════════════════════════════════════

def group_leader_ui():
    st.title("⛳ Capturar Scores — Grupo")

    # ── Restaurar sesión desde query params (persiste al bloquear celular) ──
    if not ss_get("group_auth"):
        params = st.query_params
        code_from_url = params.get("code", None)
        if code_from_url and not ss_get("_restoring_code"):
            ss_set("_restoring_code", True)
            result = db.get_group_by_code(code_from_url)
            if result:
                ss_set("group_auth", {"group": result["group"], "torneo": result["torneo"]})
                ss_set("_restoring_code", False)
                st.rerun()
            else:
                ss_set("_restoring_code", False)

    if ss_get("group_auth"):
        group = ss_get("group_auth")["group"]
        torneo = ss_get("group_auth")["torneo"]
        st.success(f"✅ {group['name']} — {torneo['name']}")
        if st.button("🔄 Cambiar grupo"):
            ss_set("group_auth", None)
            st.query_params.clear()
            st.rerun()
        _capture_group_scores(torneo, group)
        return

    st.markdown("Ingresa el código de tu grupo:")
    code = st.text_input("Código de grupo", max_chars=6, placeholder="123456")

    if st.button("Entrar", type="primary"):
        if not code or len(code) != 6 or not code.isdigit():
            st.error("El código debe ser de 6 dígitos numéricos.")
            return
        result = db.get_group_by_code(code)
        if not result:
            st.error("Código no encontrado.")
            return
        group = result["group"]
        torneo = result["torneo"]
        ss_set("group_auth", {"group": group, "torneo": torneo})
        # Guardar en URL para sobrevivir recargas / bloqueo de pantalla
        st.query_params["code"] = code
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

def main():
    st.sidebar.title("⛳ Stableford")
    vista = st.sidebar.radio("Vista", ["🏆 Leaderboard", "🎯 Capturar (Grupo)", "🔐 Admin"])

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
    elif vista == "🎯 Capturar (Grupo)":
        group_leader_ui()
    else:
        leaderboard_ui()

if __name__ == "__main__":
    main()
