"""
🎯 JOB COPILOT — Interface de candidature
Zein ELAJAMY | Ingénieur R&D | ENSEM 2026
Frontend premium inspiré des standards Apple / Indeed / Nike.
"""

import asyncio
import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from engine.database import STATUS_EMOJI, VALID_STATUSES, JobDatabase
from engine.sourcing_jobspy import scan_all_france

# ─── PAGE CONFIG ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Copilot — Zein ELAJAMY",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    :root {
        --bg: #0b1220;
        --panel: rgba(15, 23, 42, 0.72);
        --panel-strong: #111827;
        --stroke: rgba(148, 163, 184, 0.18);
        --text: #e5eefb;
        --muted: #94a3b8;
        --brand: #60a5fa;
        --brand-2: #38bdf8;
        --good: #22c55e;
        --warn: #f59e0b;
        --bad: #ef4444;
    }

    html, body, [class*="css"] {
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(96,165,250,0.16), transparent 35%),
            radial-gradient(circle at top right, rgba(56,189,248,0.12), transparent 30%),
            linear-gradient(180deg, #08101e 0%, #0b1220 100%);
        color: var(--text);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.12);
    }

    [data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }

    .hero {
        background: linear-gradient(135deg, rgba(15,23,42,0.92), rgba(17,24,39,0.86));
        border: 1px solid rgba(148,163,184,0.16);
        border-radius: 24px;
        padding: 28px 30px;
        margin: 0 0 18px 0;
        box-shadow: 0 20px 50px rgba(0,0,0,0.28);
    }

    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.05;
        letter-spacing: -0.04em;
        color: white;
        margin-bottom: 0.25rem;
    }

    .hero-subtitle {
        font-size: 1.0rem;
        color: var(--muted);
        line-height: 1.45;
    }

    .section-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148,163,184,0.14);
        border-radius: 20px;
        padding: 18px;
        box-shadow: 0 14px 35px rgba(0,0,0,0.18);
    }

    .metric-card {
        background: linear-gradient(180deg, rgba(17,24,39,0.92), rgba(15,23,42,0.88));
        border-radius: 18px;
        padding: 18px 16px;
        text-align: left;
        border: 1px solid rgba(148,163,184,0.14);
        margin-bottom: 10px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        min-height: 112px;
    }

    .metric-kicker {
        font-size: 0.76rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        margin-bottom: 4px;
    }

    .metric-value {
        font-size: 2.1rem;
        line-height: 1;
        font-weight: 800;
        color: white;
    }

    .metric-label {
        font-size: 0.85rem;
        color: var(--muted);
        margin-top: 6px;
    }

    .pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 12px;
        border-radius: 999px;
        border: 1px solid rgba(148,163,184,0.16);
        background: rgba(15,23,42,0.75);
        color: #dbeafe;
        font-size: 0.82rem;
        font-weight: 600;
    }

    .job-card {
        background: linear-gradient(180deg, rgba(17,24,39,0.92), rgba(15,23,42,0.84));
        border-radius: 18px;
        padding: 16px 18px;
        margin: 10px 0;
        border: 1px solid rgba(148,163,184,0.14);
        box-shadow: 0 10px 30px rgba(0,0,0,0.18);
    }

    .job-card strong {
        font-size: 1.02rem;
        letter-spacing: -0.01em;
        color: white;
    }

    .score-high {
        background: rgba(34,197,94,0.15);
        color: #86efac;
        padding: 4px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.82rem;
        border: 1px solid rgba(34,197,94,0.24);
    }

    .score-mid {
        background: rgba(245,158,11,0.15);
        color: #fbbf24;
        padding: 4px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.82rem;
        border: 1px solid rgba(245,158,11,0.24);
    }

    .score-low {
        background: rgba(239,68,68,0.14);
        color: #fca5a5;
        padding: 4px 10px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.82rem;
        border: 1px solid rgba(239,68,68,0.24);
    }

    .stButton > button {
        border-radius: 14px;
        font-weight: 700;
        padding: 0.8rem 1rem;
        border: 1px solid rgba(148,163,184,0.14);
        background: linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%);
        color: white;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 12px 28px rgba(37,99,235,0.28);
    }

    .stMetric {
        background: transparent;
    }

    [data-testid="stDataFrame"] {
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid rgba(148,163,184,0.14);
        box-shadow: 0 12px 30px rgba(0,0,0,0.16);
    }

    [data-testid="stExpander"] {
        border-radius: 16px;
        border: 1px solid rgba(148,163,184,0.12);
        background: rgba(15,23,42,0.62);
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)


# ─── DB & HELPERS ────────────────────────────────────────────────
@st.cache_resource
def get_db() -> JobDatabase:
    return JobDatabase(str(ROOT / "storage" / "jobs.db"))


db = get_db()


def load_profile() -> dict:
    with open(ROOT / "profiles" / "master_profile.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_search_config() -> dict:
    import yaml

    path = ROOT / "profiles" / "search_config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_search_config(cfg: dict) -> None:
    import yaml

    path = ROOT / "profiles" / "search_config.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


# ─── SIDEBAR ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎯 Job Copilot")
    st.markdown("**Zein ELAJAMY**")
    st.markdown("*Ingénieur R&D | ENSEM 2026*")
    st.markdown(
        '<span class="pill">🇫🇷 France · CDI · mobilité nationale</span>',
        unsafe_allow_html=True,
    )
    st.divider()

    stats = db.get_stats()
    st.metric("📋 Offres", stats["total"])
    st.metric("📤 Candidatures", stats["sent"])
    st.metric("🎤 Entretiens", stats["interviews"])

    st.divider()

    page = st.radio(
        "Navigation",
        options=[
            "🏠 Dashboard",
            "🔍 Scanner",
            "📋 Offres",
            "⚡ Générer",
            "📊 Tracker",
            "👤 Profil",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"MAJ : {datetime.now().strftime('%d/%m %H:%M')}")


# ═══════════════════════════════════════════════════════════════
# PAGE : DASHBOARD
# ═══════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    # --- États du filtre ---
    if "dashboard_filter" not in st.session_state:
        st.session_state["dashboard_filter"] = "Toutes"
    if "location_filter" not in st.session_state:
        st.session_state["location_filter"] = None
    if "today_only" not in st.session_state:
        st.session_state["today_only"] = False

    # Header avec bouton de Scan
    h1, h2 = st.columns([4, 1])
    with h1:
        st.markdown(
            """
            <div class="hero">
                <div class="hero-title">Tableau de bord candidature</div>
                <div class="hero-subtitle">Contrôle tes candidatures, analyse le marché et propulse ta recherche.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h2:
        if st.button("🔍 SCAN OFFRES", use_container_width=True, type="primary"):
            with st.status("Recherche en cours...", expanded=True) as status:
                from engine.sourcing_jobspy import scan_all_france
                new_jobs = scan_all_france()
                db.upsert_jobs(new_jobs)
                status.update(label="Scan terminé !", state="complete", expanded=False)
                st.rerun()

    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (stats["total"], "Sourcing", "#38bdf8", "Flux", "Toutes"),
        (stats["by_status"].get("new", 0), "Sélection", "#f59e0b", "Tri", "new"),
        (stats["by_status"].get("generated", 0), "Production", "#60a5fa", "CVs", "generated"),
        (stats["sent"], "Envoi", "#22c55e", "Postulé", "sent"),
        (stats["interviews"], "Résultat", "#a855f7", "Entretiens", "interview"),
    ]
    
    for col, (val, label, color, kicker, status_key) in zip([c1, c2, c3, c4, c5], kpis):
        with col:
            # On utilise une carte stylée mais avec un bouton masqué pour l'interaction
            active_border = "3px solid " + color if st.session_state["dashboard_filter"] == status_key else "1px solid rgba(148,163,184,0.14)"
            st.markdown(
                f"""<div class="metric-card" style="border: {active_border}; cursor: pointer;">
                <div class="metric-kicker">{kicker}</div>
                <div class="metric-value" style="color:{color}">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""",
                unsafe_allow_html=True,
            )
            if st.button(f"VOIR {label.upper()}", key=f"btn_{status_key}", use_container_width=True):
                st.session_state["dashboard_filter"] = status_key
                st.session_state["location_filter"] = None
                st.rerun()

    if st.session_state["dashboard_filter"] != "Toutes" or st.session_state["location_filter"]:
        if st.button("🔄 RÉINITIALISER TOUS LES FILTRES", type="primary", use_container_width=True):
            st.session_state["dashboard_filter"] = "Toutes"
            st.session_state["location_filter"] = None
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns([1.8, 1])

    with col_l:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        
        # Sélecteur de vue
        header_col, filter_col = st.columns([1.1, 1.4])
        with header_col:
            st.subheader("🎯 Sélection d'offres")
        with filter_col:
            c_view, c_today = st.columns([1, 1])
            with c_view:
                view_mode = st.radio("Affichage", ["🔥 Top", "🆕 Toutes"], horizontal=True, label_visibility="collapsed")
            with c_today:
                st.session_state["today_only"] = st.toggle("📅 Aujourd'hui", value=st.session_state["today_only"])

        # Calcul de la liste
        filt_status = st.session_state["dashboard_filter"]
        filt_loc = st.session_state["location_filter"]
        
        if view_mode == "🔥 Top":
            # Le top ignore un peu les filtres pour rester pertinent, mais on peut les appliquer
            jobs_to_show = db.get_top_to_apply(n=12)
        else:
            status_val = None if filt_status == "Toutes" else filt_status
            jobs_to_show = db.get_jobs(status=status_val, location_filter=filt_loc, limit=60)

        if st.session_state["today_only"]:
            today = date.today().isoformat()
            jobs_to_show = [j for j in jobs_to_show if j.get("sourcing_date") == today]

        # Titre dynamique de la liste
        active_filters = []
        if st.session_state["dashboard_filter"] != "Toutes": active_filters.append(st.session_state['dashboard_filter'].upper())
        if st.session_state["location_filter"]: active_filters.append(st.session_state['location_filter'].upper())
        
        if active_filters:
            st.info(f"Filtre actif : {' + '.join(active_filters)}. Clique sur SOURCING ou la ville pour réinitialiser.")

        if not jobs_to_show:
            st.info("Aucune offre. Lance un scan → **🔍 Scanner**")
        else:
            for j in jobs_to_show:
                s = j["fit_score"]
                cls = ("score-high" if s >= 70 else "score-mid" if s >= 50 else "score-low")
                url_btn = (f'<a href="{j["url"]}" target="_blank" style="color:#60a5fa;text-decoration:none;font-weight:700">Postuler ↗</a>' if j.get("url") else "")
                
                # Formatage de la date
                try:
                    dt = datetime.strptime(j.get("sourcing_date", ""), "%Y-%m-%d")
                    date_str = dt.strftime("%d %b")
                except:
                    date_str = "Récemment"

                skills_str = ", ".join(j.get("matched_skills", [])[:6])
                
                st.markdown(
                    f"""<div class="job-card">
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;">
                        <div style="flex:1">
                            <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
                                <span class="{cls}">{s}%</span>
                                <span style="color:var(--muted); font-size:0.8rem;">📅 {date_str}</span>
                                <span style="background:rgba(148,163,184,0.1); padding:2px 8px; border-radius:4px; font-size:0.7rem; color:var(--muted)">{j.get("source", "").upper()}</span>
                            </div>
                            <strong style="color:white; font-size:1.05rem;">{j["title"][:70]}</strong><br>
                            <span style="color:var(--brand); font-weight:600; font-size:0.95rem">{j.get("company", "?")}</span>
                            <span style="color:var(--muted); font-size:0.9rem"> · 📍 {j.get("location", "?")}</span><br>
                            <div style="margin-top:8px; line-height:1.4">
                                <small style="color:#93c5fd; font-size:0.82rem">✨ {skills_str}</small>
                            </div>
                        </div>
                        <div style="text-align:right;">
                            {url_btn}
                        </div>
                    </div>
                </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("💡 Analyse du Marché")
        st.caption("Compétences les plus demandées dans tes 200+ offres.")
        
        # Calcul des compétences les plus fréquentes
        all_jobs_stats = db.get_jobs(limit=500)
        skill_counts = {}
        for j in all_jobs_stats:
            for sk in j.get("matched_skills", []):
                skill_counts[sk] = skill_counts.get(sk, 0) + 1
        
        sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        
        if not sorted_skills:
            st.caption("Données insuffisantes pour l'analyse.")
        else:
            for sk_name, count in sorted_skills:
                pct = round(count / len(all_jobs_stats) * 100) if all_jobs_stats else 0
                st.markdown(f"""
                    <div style="margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:2px;">
                            <span style="color:white">{sk_name}</span>
                            <span style="color:var(--muted)">{pct}%</span>
                        </div>
                        <div style="background:rgba(96,165,250,0.1); height:4px; border-radius:2px;">
                            <div style="background:var(--brand); width:{pct}%; height:4px; border-radius:2px;"></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        st.divider()
        st.subheader("📍 Mobilité")
        st.caption("Filtre tes offres par zone géographique.")
        locs = db.count_by_location()
        if not locs:
            st.caption("Aucune donnée.")
        else:
            for loc in locs:
                l_name = loc["location"]
                l_count = loc["cnt"]
                is_active = st.session_state["location_filter"] == l_name
                btn_label = f"{l_name} ({l_count})"
                if st.button(btn_label, key=f"loc_{l_name}", use_container_width=True, type="secondary" if not is_active else "primary"):
                    if is_active:
                        st.session_state["location_filter"] = None
                    else:
                        st.session_state["location_filter"] = l_name
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# PAGE : SCANNER
# ═══════════════════════════════════════════════════════════════
elif page == "🔍 Scanner":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Scanner le marché</div>
            <div class="hero-subtitle">
                Recherche multi-sources pour trouver les meilleures opportunités en France, avec un tri orienté pertinence.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cfg = load_search_config()
    search_cfg = cfg.get("search", {})
    filter_cfg = cfg.get("filters", {})

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("#### 🔎 Mots-clés")
        kw_text = st.text_area(
            "keywords",
            value="\n".join(search_cfg.get("keywords", [])),
            height=220,
            label_visibility="collapsed",
        )

        st.markdown("#### 📍 Villes cibles")
        all_locs = search_cfg.get("locations", ["France"])
        priority = [
            "Paris, France",
            "Lyon, France",
            "Marseille, France",
            "Toulouse, France",
            "Bordeaux, France",
            "Nice, France",
            "Montpellier, France",
            "Grenoble, France",
            "France",
        ]
        selected_locs = st.multiselect(
            "villes",
            options=all_locs,
            default=[c for c in priority if c in all_locs],
            label_visibility="collapsed",
        )

    with col2:
        st.markdown("#### ⚙️ Paramètres")
        days = st.slider("Offres des X derniers jours", 1, 30, 7)
        results_per_q = st.slider("Résultats par requête", 5, 50, 20)
        min_score = st.slider(
            "Score minimum (%)",
            0,
            80,
            int(filter_cfg.get("min_score", 40)),
        )

        st.markdown("#### 📡 Sources")
        st.markdown(
            '<span class="pill">LinkedIn</span> <span class="pill">Indeed</span> <span class="pill">Google Jobs</span> <span class="pill">France Travail</span>',
            unsafe_allow_html=True,
        )
        st.caption("Toutes actives via JobSpy")

    st.divider()

    cscan1, cscan2, cscan3 = st.columns([1.15, 1, 1])
    with cscan1:
        if st.button("🚀 LANCER LE SCAN", type="primary", use_container_width=True):
            keywords = [k.strip() for k in kw_text.split("\n") if k.strip()]

            if not keywords:
                st.error("Ajoute au moins un mot-clé.")
            elif not selected_locs:
                st.error("Sélectionne au moins une ville.")
            else:
                new_cfg = dict(cfg)
                new_cfg["search"] = dict(search_cfg)
                new_cfg["search"]["keywords"] = keywords
                new_cfg["search"]["locations"] = selected_locs
                new_cfg["search"]["hours_old"] = days * 24
                new_cfg["search"]["results_per_query"] = results_per_q
                new_cfg.setdefault("filters", {})["min_score"] = min_score
                save_search_config(new_cfg)

                prog = st.progress(0, text="Démarrage...")
                msg_area = st.empty()

                def cb(p: float, msg: str) -> None:
                    prog.progress(p, text=msg)
                    msg_area.markdown(f"*{msg}*")

                try:
                    with st.spinner("Scan multi-sources en cours..."):
                        jobs = scan_all_france(progress_callback=cb)

                    if jobs:
                        added = db.upsert_jobs(jobs)
                        st.success(
                            f"✅ **{len(jobs)}** offres trouvées — **{added}** nouvelles ajoutées"
                        )

                        st.subheader("🏆 Top offres trouvées")
                        rows = []
                        for j in jobs[:20]:
                            rows.append(
                                {
                                    "Score": f"{j['fit_score']}%",
                                    "Poste": j["title"][:50],
                                    "Entreprise": j.get("company", "?")[:30],
                                    "Ville": j.get("location", "?")[:25],
                                    "Source": j.get("source", "").upper(),
                                }
                            )
                        st.dataframe(
                            pd.DataFrame(rows),
                            hide_index=True,
                            use_container_width=True,
                        )
                        st.info(
                            "👉 Va dans **📋 Offres** pour générer tes candidatures !"
                        )
                    else:
                        st.warning(
                            "Aucune offre. Élargis les critères ou vérifie ta connexion."
                        )

                except Exception as e:
                    st.error(f"❌ Erreur : {e}")
                    import traceback

                    st.code(traceback.format_exc())
    with cscan2:
        st.markdown(
            """
            <div class="section-card">
                <div class="metric-kicker">Flux</div>
                <div class="metric-value">4</div>
                <div class="metric-label">Sources actives</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cscan3:
        st.markdown(
            """
            <div class="section-card">
                <div class="metric-kicker">Conseil</div>
                <div class="metric-label" style="font-size:0.95rem;line-height:1.5;">
                    Lance des scans courts et répétés pour garder les offres fraîches et pertinentes.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════
# PAGE : OFFRES
# ═══════════════════════════════════════════════════════════════
elif page == "📋 Offres":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Offres disponibles</div>
            <div class="hero-subtitle">
                Une vue claire, premium et orientée action pour identifier rapidement les meilleurs postes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        search_q = st.text_input("🔍 Rechercher", placeholder="titre, entreprise...")
    with c2:
        f_status = st.selectbox("Statut", ["Tous"] + VALID_STATUSES)
    with c3:
        cities = [
            "Toute la France",
            "Paris",
            "Lyon",
            "Marseille",
            "Toulouse",
            "Bordeaux",
            "Nice",
            "Montpellier",
            "Grenoble",
        ]
        f_city = st.selectbox("Ville", cities)
    with c4:
        min_s = st.slider("Score min", 0, 100, 40)

    jobs = db.get_jobs(
        min_score=min_s,
        status=f_status if f_status != "Tous" else None,
        location_filter=f_city if f_city != "Toute la France" else None,
        search=search_q or None,
        limit=300,
    )

    st.markdown(
        f'<span class="pill">{len(jobs)} offres visibles</span>', unsafe_allow_html=True
    )

    if not jobs:
        st.info("Lance un scan d'abord → **🔍 Scanner**")
    else:
        rows = []
        for j in jobs:
            rows.append(
                {
                    "Score": j["fit_score"],
                    "Statut": STATUS_EMOJI.get(j["status"], "•") + " " + j["status"],
                    "Poste": j["title"][:55],
                    "Entreprise": j.get("company", "?")[:30],
                    "Ville": j.get("location", "?")[:25],
                    "Source": j.get("source", "").upper(),
                    "_id": j["id"],
                }
            )

        df = pd.DataFrame(rows)
        st.dataframe(
            df.drop(columns=["_id"]),
            hide_index=True,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        # Sélection assistée via session_state si dispo
        if len(jobs) > 0:
            selected_job = jobs[0]
            st.divider()

            col_d, col_a = st.columns([2, 1])

            with col_d:
                s = selected_job["fit_score"]
                ico = "🟢" if s >= 70 else "🟡" if s >= 50 else "🔴"
                st.markdown(f"## {ico} {selected_job['title']}")
                st.markdown(
                    f"**{selected_job.get('company', '?')}** — 📍 {selected_job.get('location', '?')}"
                )
                if selected_job.get("url"):
                    st.markdown(f"🔗 [Voir l'offre originale]({selected_job['url']})")
                m = selected_job.get("matched_skills", [])
                if m:
                    st.markdown(
                        "**Skills matchés :** " + " ".join([f"`{sk}`" for sk in m[:8]])
                    )
                desc = selected_job.get("description", "")
                if desc:
                    with st.expander("📄 Description complète"):
                        st.markdown(desc[:3000])

            with col_a:
                st.markdown("### Actions")
                cur = selected_job["status"]
                new_s = st.selectbox(
                    "Statut",
                    VALID_STATUSES,
                    index=VALID_STATUSES.index(cur) if cur in VALID_STATUSES else 0,
                    key=f"sel_status_{selected_job['id']}",
                )
                notes = st.text_area(
                    "Notes",
                    value=selected_job.get("notes", "") or "",
                    height=80,
                    key=f"sel_notes_{selected_job['id']}",
                )
                if st.button(
                    "💾 Sauvegarder",
                    use_container_width=True,
                    key=f"sel_save_{selected_job['id']}",
                ):
                    db.update_status(selected_job["id"], new_s, notes)
                    st.success("✅ Mis à jour !")
                    st.rerun()

                st.divider()

                if st.button(
                    "⚡ Générer CV + Lettre",
                    type="primary",
                    use_container_width=True,
                    key=f"sel_gen_{selected_job['id']}",
                ):
                    st.session_state["generate_job"] = selected_job
                    st.rerun()

                if selected_job.get("url"):
                    st.link_button(
                        "🌐 Postuler en ligne",
                        selected_job["url"],
                        use_container_width=True,
                    )


# ═══════════════════════════════════════════════════════════════
# PAGE : GÉNÉRER
# ═══════════════════════════════════════════════════════════════
elif page == "⚡ Générer":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Génération de candidature</div>
            <div class="hero-subtitle">
                Génère un CV adapté, propre et prêt à l'envoi, avec un aperçu clair avant téléchargement.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    job = st.session_state.get("generate_job", None)

    if not job:
        tab1, tab2 = st.tabs(["📋 Depuis les offres scannées", "✍️ Saisie manuelle"])

        with tab1:
            top = db.get_top_to_apply(n=30)
            if not top:
                st.info("Lance d'abord un scan → **🔍 Scanner**")
            else:
                opts = {
                    f"[{j['fit_score']}%] {j['title']} @ {j['company']}": j for j in top
                }
                choice = st.selectbox("Sélectionne une offre", list(opts.keys()))
                if st.button("✅ Utiliser cette offre", type="primary"):
                    st.session_state["generate_job"] = opts[choice]
                    st.rerun()

        with tab2:
            with st.form("manual_form"):
                col1, col2 = st.columns(2)
                with col1:
                    m_title = st.text_input(
                        "Poste *", placeholder="Ingénieur R&D Simulation"
                    )
                    m_company = st.text_input(
                        "Entreprise", placeholder="Airbus, EDF, TotalEnergies..."
                    )
                    m_loc = st.text_input("Ville", placeholder="Toulouse")
                with col2:
                    m_url = st.text_input("URL de l'offre", placeholder="https://...")
                    m_skills = st.text_input(
                        "Compétences clés", placeholder="Ansys, Python, CFD..."
                    )
                m_desc = st.text_area(
                    "Description de l'offre (copie-colle)", height=200
                )

                submitted = st.form_submit_button(
                    "✅ Utiliser cette offre", type="primary"
                )
                if submitted:
                    if not m_title:
                        st.error("Le poste est obligatoire.")
                    else:
                        job = {
                            "id": f"MAN-{abs(hash(m_title + m_company))}",
                            "title": m_title,
                            "company": m_company or "Non précisé",
                            "location": m_loc or "France",
                            "description": m_desc,
                            "required_skills": [
                                s.strip() for s in m_skills.split(",") if s.strip()
                            ],
                            "matched_skills": [],
                            "fit_score": 80,
                            "source": "manuel",
                            "url": m_url or "",
                        }
                        st.session_state["generate_job"] = job
                        st.rerun()

    if job:
        col_info, col_gen = st.columns([2, 1])

        with col_info:
            s = job.get("fit_score", 0)
            ico = "🟢" if s >= 70 else "🟡" if s >= 50 else "🔴"
            st.markdown(f"### {ico} {job['title']}")
            st.markdown(
                f"**{job.get('company', '?')}** — 📍 {job.get('location', '?')} — Score : **{s}%**"
            )
            m = job.get("matched_skills", [])
            if m:
                st.markdown("Skills matchés : " + " ".join([f"`{sk}`" for sk in m[:8]]))
            if job.get("url"):
                st.markdown(f"🔗 [Voir l'offre]({job['url']})")

            st.markdown(
                '<span class="pill">Aperçu immédiat · téléchargement · envoi</span>',
                unsafe_allow_html=True,
            )

            if st.button("🔄 Changer d'offre", use_container_width=True):
                st.session_state.pop("generate_job", None)
                st.session_state.pop("last_gen", None)
                st.rerun()

        with col_gen:
            st.markdown("### ⚙️ Options")
            gen_cv = st.checkbox("📄 CV PDF (Typst)", value=True)
            gen_letter = st.checkbox("✉️ Lettre de motivation", value=True)
            use_llm = st.checkbox("🤖 LLM (lent, meilleur)", value=False)

            if st.button("🚀 GÉNÉRER", type="primary", use_container_width=True):
                with st.spinner("Génération en cours..."):
                    try:
                        profile = load_profile()

                        cv_result: dict = {}
                        if gen_cv:
                            from engine.cv_generator import PersonalCVGenerator

                            gen_obj = PersonalCVGenerator()
                            cv_result = asyncio.run(gen_obj.generate_cv_for_job(job))

                        letter_text = ""
                        letter_path = ""
                        if gen_letter:
                            if use_llm and cv_result.get("cv_data"):
                                try:
                                    from batch_apply import generate_cover_letter_llm
                                    from engine.cv_generator import (
                                        PersonalCVGenerator as _CG,
                                    )

                                    letter_text = (
                                        asyncio.run(
                                            generate_cover_letter_llm(
                                                _CG(), profile, job
                                            )
                                        )
                                        or ""
                                    )
                                except Exception:
                                    pass

                            if not letter_text:
                                from batch_apply import generate_cover_letter_heuristic

                                letter_text = generate_cover_letter_heuristic(
                                    profile, job
                                )

                            safe = "".join(
                                c if c.isalnum() or c in "._-" else "_"
                                for c in f"{job.get('company', 'job')}_{job.get('title', 'cv')}"
                            )[:60]
                            out_dir = ROOT / "output" / safe
                            out_dir.mkdir(parents=True, exist_ok=True)
                            letter_path = str(out_dir / "lettre.txt")
                            Path(letter_path).write_text(letter_text, encoding="utf-8")

                        cv_path = (
                            cv_result.get("pdf_path") or cv_result.get("markdown") or ""
                        )
                        db.save_generation(job["id"], cv_path, letter_path)

                        st.success("✅ Candidature générée !")
                        st.session_state["last_gen"] = {
                            "cv_result": cv_result,
                            "letter_text": letter_text,
                            "letter_path": letter_path,
                            "cv_path": cv_path,
                        }

                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")
                        import traceback

                        st.code(traceback.format_exc())

        last = st.session_state.get("last_gen")
        if last:
            st.divider()
            st.subheader("📥 Téléchargements")

            d1, d2, d3 = st.columns(3)

            with d1:
                cv_path = last.get("cv_path", "")
                if cv_path and Path(cv_path).exists():
                    with open(cv_path, "rb") as f:
                        ext = Path(cv_path).suffix
                        mime = "application/pdf" if ext == ".pdf" else "text/plain"
                        st.download_button(
                            "📄 Télécharger CV",
                            data=f.read(),
                            file_name=f"CV_Zein_{job.get('company', '')}_{job.get('title', '')}{ext}"[
                                :80
                            ],
                            mime=mime,
                            use_container_width=True,
                            type="primary",
                        )
                else:
                    st.info("CV non disponible (Typst manquant ?)")

            with d2:
                lt = last.get("letter_text", "")
                if lt:
                    st.download_button(
                        "✉️ Télécharger Lettre",
                        data=lt.encode("utf-8"),
                        file_name=f"Lettre_{job.get('company', '')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

            with d3:
                if job.get("url"):
                    st.link_button(
                        "🌐 Postuler maintenant",
                        job["url"],
                        use_container_width=True,
                    )

            if last.get("letter_text"):
                with st.expander("👁️ Aperçu de la lettre"):
                    st.text(last["letter_text"])

            st.divider()
            ca, cb_ = st.columns(2)
            with ca:
                if st.button(
                    "✅ Marquer comme envoyée", type="primary", use_container_width=True
                ):
                    db.update_status(job["id"], "sent")
                    st.session_state.pop("generate_job", None)
                    st.session_state.pop("last_gen", None)
                    st.success("✅ Candidature enregistrée !")
                    st.rerun()
            with cb_:
                if st.button("🔄 Générer une autre offre", use_container_width=True):
                    st.session_state.pop("generate_job", None)
                    st.session_state.pop("last_gen", None)
                    st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE : TRACKER
# ═══════════════════════════════════════════════════════════════
elif page == "📊 Tracker":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Suivi des candidatures</div>
            <div class="hero-subtitle">
                Vue claire et rapide pour piloter les envois, les retours et les prochaines actions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    sent = stats["sent"]
    inter = stats["interviews"]
    off = stats["offers"]

    with c1:
        st.markdown(
            '<div class="metric-card"><div class="metric-kicker">Pipeline</div>',
            unsafe_allow_html=True,
        )
        st.metric("📤 Envoyées", sent)
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.metric("🎤 Entretiens", inter)
    with c3:
        st.metric("🎉 Offres", off)
    with c4:
        taux = round(inter / sent * 100, 1) if sent > 0 else 0
        st.metric("📈 Taux entretien", f"{taux}%")

    st.divider()

    filter_tab = st.radio(
        "Filtrer",
        [
            "Tous",
            "sent",
            "applied",
            "interview",
            "offer",
            "rejected",
            "generated",
            "new",
        ],
        horizontal=True,
        format_func=lambda x: (
            f"{STATUS_EMOJI.get(x, '•')} {x}" if x != "Tous" else "📋 Tous"
        ),
    )

    tracker_jobs = db.get_jobs(
        status=filter_tab if filter_tab != "Tous" else None,
        limit=200,
    )

    if not tracker_jobs:
        st.info("Aucune candidature ici pour l'instant.")
    else:
        st.markdown(f"**{len(tracker_jobs)} candidature(s)**")
        for j in tracker_jobs:
            label = (
                f"{STATUS_EMOJI.get(j['status'], '•')} "
                f"[{j['fit_score']}%] {j['title']} — "
                f"{j.get('company', '?')} | {j.get('location', '?')}"
            )
            with st.expander(label, expanded=False):
                ci, cu = st.columns([2, 1])

                with ci:
                    if j.get("url"):
                        st.markdown(f"🔗 [Voir l'offre]({j['url']})")
                    if j.get("applied_date"):
                        st.markdown(f"📅 Postulé le : {j['applied_date']}")
                    if j.get("response_date"):
                        st.markdown(f"📬 Réponse le : {j['response_date']}")
                    if j.get("notes"):
                        st.markdown(f"📝 {j['notes']}")

                    cv_p = j.get("cv_path", "")
                    if cv_p and Path(cv_p).exists():
                        with open(cv_p, "rb") as f:
                            st.download_button(
                                "📄 CV",
                                data=f.read(),
                                file_name=Path(cv_p).name,
                                key=f"trk_dl_{j['id']}",
                            )

                with cu:
                    ns = st.selectbox(
                        "Statut",
                        VALID_STATUSES,
                        index=VALID_STATUSES.index(j["status"])
                        if j["status"] in VALID_STATUSES
                        else 0,
                        key=f"trk_s_{j['id']}",
                    )
                    nn = st.text_input(
                        "Notes",
                        value=j.get("notes", "") or "",
                        key=f"trk_n_{j['id']}",
                    )
                    if st.button(
                        "💾 Mettre à jour",
                        key=f"trk_b_{j['id']}",
                        use_container_width=True,
                    ):
                        db.update_status(j["id"], ns, nn)
                        st.success("✅")
                        st.rerun()

                    if j.get("url"):
                        st.link_button("🌐 Offre", j["url"], use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# PAGE : PROFIL
# ═══════════════════════════════════════════════════════════════
elif page == "👤 Profil":
    st.markdown(
        """
        <div class="hero">
            <div class="hero-title">Mon profil</div>
            <div class="hero-subtitle">
                Mets à jour ton identité, ton positionnement et tes informations de candidature sans toucher au JSON manuellement.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    profile = load_profile()
    identity = profile.get("identity", {})

    left, right = st.columns([1.2, 0.8])

    with left:
        left, right = st.columns([1.2, 0.8])

        with left:
            with st.form("profil_form"):
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.subheader("📋 Identité")
                c1, c2 = st.columns(2)
                with c1:
                    name = st.text_input("Nom complet", value=identity.get("name", ""))
                    email = st.text_input("Email", value=identity.get("email", ""))
                    phone = st.text_input("Téléphone", value=identity.get("phone", ""))
                with c2:
                    loc = st.text_input(
                        "Localisation", value=identity.get("location", "")
                    )
                    linkedin = st.text_input(
                        "LinkedIn URL", value=identity.get("linkedin", "") or ""
                    )
                    github = st.text_input(
                        "GitHub URL", value=identity.get("github", "") or ""
                    )

                st.subheader("📝 Positionnement")
                headline = st.text_input(
                    "Headline (titre CV)", value=profile.get("headline", "")
                )
                summary = st.text_area(
                    "Résumé professionnel", value=profile.get("summary", ""), height=120
                )
                cur_status = st.text_input(
                    "Statut actuel", value=profile.get("current_status", "")
                )

                submitted = st.form_submit_button(
                    "💾 Sauvegarder", type="primary", use_container_width=True
                )
                st.markdown("</div>", unsafe_allow_html=True)

                if submitted:
                    profile["identity"].update(
                        {
                            "name": name,
                            "email": email,
                            "phone": phone,
                            "location": loc,
                            "linkedin": linkedin or None,
                            "github": github or None,
                        }
                    )
                    profile["headline"] = headline
                    profile["summary"] = summary
                    profile["current_status"] = cur_status

                    with open(
                        ROOT / "config" / "master_profile.json", "w", encoding="utf-8"
                    ) as f:
                        json.dump(profile, f, indent=2, ensure_ascii=False)
                    st.success("✅ Profil sauvegardé !")
                    st.rerun()

        with right:
            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.subheader("🛠️ Compétences")
            skills = profile.get("skills", {})
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**Techniques**")
                for s in skills.get("technical", {}).keys():
                    st.markdown(f"• {s}")
            with c2:
                st.markdown("**Outils**")
                for s in skills.get("tools", {}).keys():
                    st.markdown(f"• {s}")
            with c3:
                st.markdown("**Frameworks**")
                for s in skills.get("frameworks", {}).keys():
                    st.markdown(f"• {s}")
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
