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

# ─── CSS PREMIUM (APPLE/NIKE STYLE) ──────────────────────────────
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        /* Variables Globales */
        :root {
            --brand: #38bdf8;
            --brand-glow: rgba(56, 189, 248, 0.3);
            --bg: #020617;
            --card-bg: rgba(30, 41, 59, 0.4);
            --border: rgba(148, 163, 184, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --radius: 20px;
            --transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* Reset Streamlit */
        .main {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
        }
        .stApp { background: var(--bg); }
        
        [data-testid="stHeader"] { background: transparent; }
        
        /* Correction Sidebar visible */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            border-right: 1px solid var(--border);
        }
        [data-testid="stSidebar"] * {
            color: #f8fafc !important;
            font-family: 'Outfit', sans-serif;
        }

        /* Typography */
        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em !important;
        }
        
        /* Typography overrides */
        .hero-title {
            font-size: 4rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            background: linear-gradient(to right, #ffffff, #94a3b8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.1;
        }
        .hero-subtitle {
            font-size: 1.25rem;
            color: var(--text-muted);
            max-width: 800px;
            font-weight: 300;
            line-height: 1.6;
        }
        .hero-container {
            padding: 40px 0 60px 0;
            text-align: left;
        }
        .hero-h1 {
            font-size: 64px !important;
            background: linear-gradient(to bottom, #ffffff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 15px;
            line-height: 1.1;
            font-family: 'Outfit', sans-serif !important;
            font-weight: 800;
        }
        .hero-h2 {
            font-size: 20px !important;
            color: var(--text-muted);
            font-weight: 300 !important;
            max-width: 600px;
            font-family: 'Outfit', sans-serif !important;
        }

        /* Premium Cards */
        .section-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            margin-bottom: 24px;
            transition: var(--transition);
        }
        .section-card:hover {
            border-color: rgba(56, 189, 248, 0.3);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }

        /* Metric Cards (KPIs) - Old vs New overrides */
        .metric-card {
            background: rgba(15, 23, 42, 0.5);
            border-radius: 20px;
            padding: 24px 20px;
            text-align: left;
            border: 1px solid var(--border);
            margin-bottom: 12px;
            transition: var(--transition);
            min-height: 120px;
            cursor: pointer;
        }
        .metric-card:hover {
            background: rgba(30, 41, 59, 0.6);
            border-color: var(--brand);
            transform: translateY(-2px);
        }
        .metric-pill {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 24px;
            text-align: center;
            transition: var(--transition);
            cursor: pointer;
        }
        .metric-pill:hover {
            background: rgba(148, 163, 184, 0.05);
            border-color: var(--brand);
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: 800;
            line-height: 1;
            color: white;
            font-family: 'Outfit', sans-serif;
            margin-bottom: 8px;
        }
        .metric-label {
            font-size: 0.9rem;
            color: var(--text-muted);
            font-weight: 600;
        }
        .metric-kicker {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }

        /* Job Cards */
        .job-card {
            background: rgba(15, 23, 42, 0.3);
            border-left: 4px solid transparent;
            border-radius: 16px;
            padding: 24px;
            margin: 16px 0;
            transition: var(--transition);
            border: 1px solid var(--border);
        }
        .job-card:hover {
            background: rgba(15, 23, 42, 0.5);
            border-left: 4px solid var(--brand);
            transform: translateX(6px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .job-card strong {
            font-size: 1.15rem;
            letter-spacing: -0.01em;
            color: white;
        }

        /* Score Tags */
        .score-high {
            background: rgba(34,197,94,0.1);
            color: #4ade80;
            padding: 4px 12px;
            border-radius: 99px;
            font-weight: 700;
            font-size: 0.85rem;
            border: 1px solid rgba(34,197,94,0.2);
        }
        .score-mid {
            background: rgba(245,158,11,0.1);
            color: #fcd34d;
            padding: 4px 12px;
            border-radius: 99px;
            font-weight: 700;
            font-size: 0.85rem;
            border: 1px solid rgba(245,158,11,0.2);
        }
        .score-low {
            background: rgba(239,68,68,0.1);
            color: #fca5a5;
            padding: 4px 12px;
            border-radius: 99px;
            font-weight: 700;
            font-size: 0.85rem;
            border: 1px solid rgba(239,68,68,0.2);
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid var(--border);
            background: rgba(15,23,42,0.8);
            color: var(--text-main);
            font-size: 0.85rem;
            font-weight: 600;
        }

        /* Custom Buttons */
        div.stButton > button {
            background: var(--text-main) !important;
            color: var(--bg) !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            padding: 12px 24px !important;
            border: none !important;
            transition: var(--transition) !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        div.stButton > button:hover {
            background: var(--brand) !important;
            transform: scale(1.02);
            box-shadow: 0 0 20px var(--brand-glow);
        }
        
        /* Form inputs overides */
        .stTextInput input, .stTextArea textarea {
            border-radius: 12px !important;
        }

        /* Hide Streamlit components gently */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        /* DO NOT HIDE HEADER -> It hides the mobile sidebar toggle! */
        /* header { visibility: hidden; } */
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
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
    # On utilise uniquement le fichier local pour garantir la synchronisation
    path = ROOT / "profiles" / "master_profile.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    st.error("❌ Profil local introuvable dans profiles/master_profile.json")
    return {}


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

def render_fill_report(fill_report: dict) -> None:
    if not fill_report:
        return
    st.caption("🧪 Fill Report")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pro", fill_report.get("pro_count", 0))
    c2.metric("Projets", fill_report.get("project_count", 0))
    c3.metric("Skills", fill_report.get("skills_total", 0))
    st.caption(
        f"floor={fill_report.get('floor_activated', False)} · "
        f"llm_calls={fill_report.get('llm_calls', 0)} · "
        f"attempt={fill_report.get('shrink_attempt', '-')}"
    )


# ─── SIDEBAR ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="padding: 20px 0;">
            <div style="font-size: 1.5rem; font-weight: 800; color: white;">JOB COPILOT</div>
            <div style="font-size: 0.85rem; color: var(--text-muted); letter-spacing: 0.05em;">ZEIN ELAJAMY — ENSEM 2026</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    page = st.radio(
        "Navigation",
        ["🏠 Dashboard", "🔍 Scanner", "📋 Offres", "⚡ Générer", "📊 Tracker", "👤 Profil"],
        label_visibility="collapsed",
    )

    st.divider()
    stats = db.get_stats()
    st.caption("STATISTIQUES")
    c1, c2 = st.columns(2)
    c1.metric("Total", stats["total"])
    c2.metric("Postulé", stats["sent"])

    st.divider()
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE : DASHBOARD
# ═══════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-h1">Bonjour, Zein.</div>
            <div class="hero-h2">
                Voici l'état de ton pipeline de recherche pour ton CDI en France en 2026.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # KPIs Row
    k1, k2, k3, k4 = st.columns(4)
    kpis = [
        (stats["total"], "Offres trouvées", "#38bdf8", "Sourcing"),
        (stats["sent"], "Candidatures", "#4ade80", "Action"),
        (stats["interviews"], "Entretiens", "#a855f7", "Progression"),
        (stats["offers"], "Offres", "#f59e0b", "Succès"),
    ]

    for col, (val, label, color, kicker) in zip([k1, k2, k3, k4], kpis):
        with col:
            st.markdown(
                f"""
                <div class="metric-card" style="border-top: 3px solid {color}">
                    <div class="metric-kicker">{kicker}</div>
                    <div class="metric-value">{val}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    col_l, col_r = st.columns([2, 1])

    with col_l:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("⭐ Offres à traiter")
        
        # BARRE DE FILTRE DASHBOARD CORRIGÉE
        dash_filter = st.radio(
            "Filtrer par statut",
            ["Top (Score > 70%)", "Tous"] + VALID_STATUSES,
            horizontal=True,
            label_visibility="collapsed",
            format_func=lambda x: f"{STATUS_EMOJI.get(x, '•')} {x.capitalize()}" if x not in ["Tous", "Top (Score > 70%)"] else x
        )
        
        location_filter = st.session_state.get("location_filter")
        if location_filter:
            st.caption(f"📍 Filtre actif : **{location_filter}**")
            if st.button("Réinitialiser le filtre mobilité", key="reset_location_filter"):
                st.session_state["location_filter"] = None
                st.rerun()

        if dash_filter == "Top (Score > 70%)":
            top_jobs = db.get_jobs(min_score=70, location_filter=location_filter, limit=200)
            display_jobs = [j for j in top_jobs if j.get("status") in {"new", "selected"}][:10]
        elif dash_filter == "Tous":
            display_jobs = db.get_jobs(location_filter=location_filter, limit=10)
        else:
            display_jobs = db.get_jobs(
                status=dash_filter,
                location_filter=location_filter,
                limit=10,
            )

        if not display_jobs:
            st.info(f"Aucune offre avec le statut '{dash_filter}'.")
        else:
            for j in display_jobs:
                score = j["fit_score"]
                s_class = (
                    "score-high"
                    if score >= 70
                    else "score-mid" if score >= 40 else "score-low"
                )

                st.markdown(
                    f"""
                    <div class="job-card">
                        <div style="display:flex; justify-content:space-between; align-items:start;">
                            <div>
                                <strong>{j['title']}</strong><br>
                                <span style="color:var(--text-muted); font-size:0.9rem;">{j.get('company', '?')} — {j.get('location', '?')}</span>
                            </div>
                            <span class="{s_class}">{score}% Fit</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button(f"Générer CV pour {j['title'][:20]}...", key=f"gen_{j['id']}"):
                        st.session_state["generate_job"] = j
                        st.session_state["page"] = "⚡ Générer"
                        st.rerun()
                with action_cols[1]:
                    if j.get("url"):
                        st.link_button("🌐 Ouvrir l'offre", j["url"], use_container_width=True)
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
                is_active = st.session_state.get("location_filter") == l_name
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
        <div class="hero-container">
            <div class="hero-h1">Scanner le marché</div>
            <div class="hero-h2">
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
        <div class="hero-container">
            <div class="hero-h1">Offres disponibles</div>
            <div class="hero-h2">
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
        for job in jobs:
            with st.container():
                col_d, col_a = st.columns([3, 1])

                with col_d:
                    s = job["fit_score"]
                    ico = "🟢" if s >= 70 else "🟡" if s >= 50 else "🔴"
                    st.markdown(f"## {ico} {job['title']}")
                    st.markdown(
                        f"**{job.get('company', '?')}** — 📍 {job.get('location', '?')}"
                    )
                    if job.get("url"):
                        st.markdown(f"🔗 [Voir l'offre originale]({job['url']})")
                    m = job.get("matched_skills", [])
                    if m:
                        st.markdown(
                            "**Skills matchés :** " + " ".join([f"`{sk}`" for sk in m[:8]])
                        )
                    desc = job.get("description", "")
                    if desc:
                        with st.expander("📄 Description complète"):
                            st.markdown(desc[:3000])

                with col_a:
                    st.markdown("### Actions")
                    cur = job["status"]
                    new_s = st.selectbox(
                        "Statut",
                        VALID_STATUSES,
                        index=VALID_STATUSES.index(cur) if cur in VALID_STATUSES else 0,
                        key=f"sel_status_{job['id']}",
                    )
                    notes = st.text_area(
                        "Notes",
                        value=job.get("notes", "") or "",
                        height=80,
                        key=f"sel_notes_{job['id']}",
                    )
                    if st.button(
                        "💾 Sauvegarder",
                        use_container_width=True,
                        key=f"sel_save_{job['id']}",
                    ):
                        db.update_status(job["id"], new_s, notes)
                        st.success("✅ Mis à jour !")
                        st.rerun()

                    st.divider()

                    if st.button(
                        "⚡ Générer CV + Lettre",
                        type="primary",
                        use_container_width=True,
                        key=f"sel_gen_{job['id']}",
                    ):
                        st.session_state["generate_job"] = job
                        st.session_state["page"] = "⚡ Générer"
                        st.rerun()


# ═══════════════════════════════════════════════════════════════
# PAGE : GÉNÉRER
# ═══════════════════════════════════════════════════════════════
elif page == "⚡ Générer":
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-h1">Génération de candidature</div>
            <div class="hero-h2">
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
            use_llm = st.checkbox("🤖 Lettre IA Premium (Gemini Cloud)", value=True)

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
                                    from Pipeline import generate_cover_letter_llm
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
                                from Pipeline import generate_cover_letter_heuristic

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
                        
                        # Debug PDF failure
                        if not cv_result.get("pdf_path") and cv_result.get("cv_data", {}).get("_last_error"):
                            st.warning(f"⚠️ Le PDF n'a pas pu être généré (Fallback Markdown) : {cv_result['cv_data']['_last_error']}")

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
            render_fill_report(last.get("cv_result", {}).get("fill_report", {}))
            
            # --- SECTION ÉDITION CHIRURGICALE ---
            cv_result = last.get("cv_result", {})
            if cv_result and cv_result.get("cv_data"):
                st.subheader("✍️ Personnalisation finale")
                cv_data = cv_result.get("cv_data", {})
                
                default_headline = cv_data.get("headline", "")
                default_summary = cv_data.get("summary", "")
                
                edited_headline = st.text_area("Accroche (Headline)", value=default_headline, height=70)
                edited_summary = st.text_area("Résumé (Summary)", value=default_summary, height=150)
                
                # Sauvegarde dans le session state pour mark_as_sent
                st.session_state["edited_headline"] = edited_headline
                st.session_state["edited_summary"] = edited_summary
                st.divider()

            st.subheader("📥 Téléchargements & Envoi")

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
                            file_name=f"CV_Zein_{job.get('company', '')}_{job.get('title', '')}{ext}"[:80],
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
                        "🌐 Voir l'offre originale",
                        job["url"],
                        use_container_width=True,
                    )

            st.divider()
            
            # --- BLOC ACTION (VOIE A) CHIRURGICAL ---
            st.markdown("### ⚡ Bloc Action (Voie A)")
            ca, cb_ = st.columns(2)
            with ca:
                if st.button("✅ J'ai postulé manuellement", type="primary", use_container_width=True):
                    db.mark_as_sent(
                        job_id=job["id"],
                        via="manual",
                        edited_headline=st.session_state.get("edited_headline"),
                        edited_summary=st.session_state.get("edited_summary"),
                        vault_path=last.get("cv_path")
                    )
                    st.session_state.pop("generate_job", None)
                    st.session_state.pop("last_gen", None)
                    st.success("✅ Candidature enregistrée ! Offre suivante...")
                    st.rerun()
            with cb_:
                st.button("🤖 Lancer l'Auto-Apply AIHawk (Bientôt)", disabled=True, use_container_width=True)

            if last.get("letter_text"):
                with st.expander("👁️ Aperçu de la lettre"):
                    st.text(last["letter_text"])


# ═══════════════════════════════════════════════════════════════
# PAGE : TRACKER
# ═══════════════════════════════════════════════════════════════
elif page == "📊 Tracker":
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-h1">Suivi des candidatures</div>
            <div class="hero-h2">
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
    taux = round(inter / sent * 100, 1) if sent > 0 else 0

    kpis_tracker = [
        (sent, "Envoyées", "#38bdf8", "Pipeline", "sent_btn"),
        (inter, "Entretiens", "#a855f7", "Progression", "inter_btn"),
        (off, "Offres", "#4ade80", "Succès", "off_btn"),
        (f"{taux}%", "Conversion", "#f59e0b", "Performance", "conv_btn"),
    ]

    for col, (val, label, color, kicker, key) in zip([c1, c2, c3, c4], kpis_tracker):
        with col:
            st.markdown(
                f"""<div class="metric-pill" style="min-height: 140px; border-color: {color}; background: rgba(15, 23, 42, 0.4);">
                <div style="font-size:11px; color:{color}; font-weight:800; text-transform:uppercase; margin-bottom:12px; letter-spacing:0.1em;">{kicker}</div>
                <div class="metric-value">{val}</div>
                <div class="metric-label">{label}</div>
            </div>""",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🔍 Gestion des candidatures")

    # Filtre style "Pills" avec st.radio horizontal
    filter_tab = st.radio(
        "Filtre rapide",
        ["Tous", "sent", "applied", "interview", "offer", "rejected", "generated", "new"],
        horizontal=True,
        label_visibility="collapsed",
        format_func=lambda x: f"{STATUS_EMOJI.get(x, '•')} {x.capitalize()}" if x != "Tous" else "📋 Tout voir"
    )

    tracker_jobs = db.get_jobs(status=filter_tab if filter_tab != "Tous" else None, limit=200)

    if not tracker_jobs:
        st.info("Aucune candidature ici pour l'instant. Le pipeline est vide.")
    else:
        st.caption(f"**{len(tracker_jobs)} itération(s)** dans ce tableau.")
        for j in tracker_jobs:
            # Score premium icon
            s = j['fit_score']
            score_icon = "🟢" if s >= 70 else "🟡" if s >= 50 else "🔴"
            
            label = f"{STATUS_EMOJI.get(j['status'], '•')} {j['title']} — {j.get('company', 'Entreprise inconnue')}"
            
            with st.expander(label, expanded=False):
                # En-tête interne stylé
                st.markdown(f"""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <div>
                        <span style="background:rgba(56, 189, 248, 0.1); color:#38bdf8; padding:4px 10px; border-radius:8px; font-size:12px; font-weight:700;">{score_icon} FIT : {s}%</span>
                        <span style="color:var(--muted); font-size:13px; margin-left:10px;">📍 {j.get('location', '?')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                ci, cu = st.columns([1.8, 1])

                with ci:
                    # Informations
                    if j.get("applied_date"): st.markdown(f"**📅 Postulé le :** `{j['applied_date']}`")
                    if j.get("response_date"): st.markdown(f"**📬 Réponse :** `{j['response_date']}`")
                    if j.get("notes"): st.markdown(f"**📝 Mémo :** {j['notes']}")

                    st.markdown("<br>", unsafe_allow_html=True)
                    # Actions rapides en ligne
                    btn_cols = st.columns(3)
                    with btn_cols[0]:
                        if j.get("url"):
                            st.link_button("🌐 Voir l'offre", j["url"], use_container_width=True)
                    with btn_cols[1]:
                        cv_p = j.get("cv_path", "")
                        if cv_p and Path(cv_p).exists():
                            with open(cv_p, "rb") as f:
                                st.download_button("📄 Mon CV", f.read(), file_name=Path(cv_p).name, key=f"trk_dl_{j['id']}", use_container_width=True)

                with cu:
                    # Zone de mise à jour (Panneau droit)
                    st.markdown('<div class="section-card" style="padding: 15px; margin-bottom:0;">', unsafe_allow_html=True)
                    ns = st.selectbox(
                        "Mettre à jour le statut",
                        VALID_STATUSES,
                        index=VALID_STATUSES.index(j["status"]) if j["status"] in VALID_STATUSES else 0,
                        key=f"trk_s_{j['id']}",
                        label_visibility="collapsed"
                    )
                    nn = st.text_input(
                        "Note rapide",
                        value=j.get("notes", "") or "",
                        key=f"trk_n_{j['id']}",
                        placeholder="Ex: Refus, Entretien prévu..."
                    )
                    if st.button("💾 Enregistrer", key=f"trk_b_{j['id']}", use_container_width=True, type="primary"):
                        db.update_status(j["id"], ns, nn)
                        st.success("Synchronisé ⚡")
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# PAGE : PROFIL
# ═══════════════════════════════════════════════════════════════
elif page == "👤 Profil":
    st.markdown(
        """
        <div class="hero-container">
            <div class="hero-h1">Mon profil</div>
            <div class="hero-h2">
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
                        ROOT / "profiles" / "master_profile.json", "w", encoding="utf-8"
                    ) as f:
                        json.dump(profile, f, indent=2, ensure_ascii=False)
                    
                    if "MASTER_PROFILE_JSON" in st.secrets:
                        st.warning("⚠️ Profil sauvegardé localement, mais attention : tu utilises un Secret Streamlit. Pense à mettre à jour ton Secret avec ces nouvelles données pour le Cloud !")
                    else:
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
