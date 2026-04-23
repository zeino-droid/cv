"""
🎯 JOB COPILOT — Studio de Candidature (Single Page)
Zein ELAJAMY | Ingénieur R&D | ENSEM 2026
Refonte SPA : Smart Match → Studio (Modale) → Archives.
"""

import asyncio
import atexit
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from engine.database import STATUS_EMOJI, JobDatabase

ASYNC_EXECUTOR = ThreadPoolExecutor(max_workers=1)
atexit.register(lambda: ASYNC_EXECUTOR.shutdown(wait=False, cancel_futures=True))


def run_coroutine_sync(coro, context: str = "operation"):
    """Run a coroutine safely in Streamlit, even if an event loop is already active."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(coro)
        except Exception as exc:
            raise RuntimeError(f"Async {context} failed: {exc}") from exc
    try:
        return ASYNC_EXECUTOR.submit(lambda: asyncio.run(coro)).result()
    except Exception as exc:
        raise RuntimeError(f"Async {context} failed: {exc}") from exc


# ─── PAGE CONFIG ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Studio de Candidature — Zein ELAJAMY",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS PREMIUM (DARK / APPLE / NIKE) ───────────────────────────
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
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

        .main { background-color: var(--bg); color: var(--text-main); font-family: 'Outfit', sans-serif; }
        .stApp { background: var(--bg); }
        [data-testid="stHeader"] { background: transparent; }

        /* Cache la sidebar (SPA) */
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { width: 0 !important; }

        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em !important;
        }

        .hero-container { padding: 32px 0 24px 0; }
        .hero-h1 {
            font-size: 56px !important;
            background: linear-gradient(to bottom, #ffffff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px; line-height: 1.1;
            font-family: 'Outfit', sans-serif !important; font-weight: 800;
        }
        .hero-h2 {
            font-size: 18px !important; color: var(--text-muted);
            font-weight: 300 !important; max-width: 720px;
            font-family: 'Outfit', sans-serif !important;
        }

        .section-card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 28px;
            margin-bottom: 24px;
        }

        .section-title {
            font-size: 0.78rem; text-transform: uppercase;
            letter-spacing: 0.14em; color: var(--brand);
            font-weight: 700; margin-bottom: 6px;
        }
        .section-h2 {
            font-size: 32px !important; color: white;
            font-weight: 800 !important; margin-bottom: 22px;
            font-family: 'Outfit', sans-serif !important;
        }

        .row-card {
            background: rgba(15, 23, 42, 0.5);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 18px;
            margin-bottom: 10px;
            transition: var(--transition);
        }
        .row-card:hover {
            border-color: var(--brand);
            background: rgba(15, 23, 42, 0.75);
        }
        .row-title { font-weight: 700; color: white; font-size: 1rem; }
        .row-meta { color: var(--text-muted); font-size: 0.85rem; margin-top: 2px; }

        .score-pill {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 0.8rem;
        }
        .score-high { background: rgba(34,197,94,0.12); color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
        .score-mid  { background: rgba(245,158,11,0.12); color: #fcd34d; border: 1px solid rgba(245,158,11,0.25); }
        .score-low  { background: rgba(239,68,68,0.12); color: #fca5a5; border: 1px solid rgba(239,68,68,0.25); }

        div.stButton > button {
            background: var(--text-main) !important;
            color: var(--bg) !important;
            border-radius: 12px !important;
            font-weight: 700 !important;
            padding: 10px 18px !important;
            border: none !important;
            transition: var(--transition) !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        div.stButton > button:hover {
            background: var(--brand) !important;
            transform: scale(1.02);
            box-shadow: 0 0 20px var(--brand-glow);
        }

        .stTextInput input, .stTextArea textarea { border-radius: 12px !important; }

        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── DB & PROFILE ────────────────────────────────────────────────
@st.cache_resource
def get_db() -> JobDatabase:
    return JobDatabase(str(ROOT / "storage" / "jobs.db"))


db = get_db()


def load_profile() -> dict:
    path = ROOT / "profiles" / "master_profile.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def score_class(score: int) -> str:
    if score >= 70:
        return "score-high"
    if score >= 40:
        return "score-mid"
    return "score-low"


def safe_filename(value: str, max_len: int = 60) -> str:
    cleaned = "".join(c if c.isalnum() or c in "._- " else "_" for c in value).strip()
    return cleaned.replace(" ", "_")[:max_len] or "file"


# ─── GÉNÉRATION (CV + LETTRE) ────────────────────────────────────
def generate_documents(job: dict, gen_cv: bool, gen_letter: bool, use_llm: bool,
                       headline_override: str | None = None,
                       summary_override: str | None = None) -> dict:
    """Lance la génération CV + lettre via les modules existants."""
    profile = load_profile()
    cv_result: dict = {}
    letter_text = ""
    cv_path = ""
    letter_path = ""

    if gen_cv:
        from engine.cv_generator import PersonalCVGenerator
        gen_obj = PersonalCVGenerator()
        cv_result = run_coroutine_sync(
            gen_obj.generate_cv_for_job(
                job,
                headline_override=headline_override or None,
                summary_override=summary_override or None,
            ),
            context="CV generation",
        )
        cv_path = (
            cv_result.get("pdf_path")
            or cv_result.get("md_path")
            or cv_result.get("markdown")
            or ""
        )

    if gen_letter:
        if use_llm:
            try:
                from Pipeline import generate_cover_letter_llm
                from engine.cv_generator import PersonalCVGenerator as _CG
                letter_text = run_coroutine_sync(
                    generate_cover_letter_llm(_CG(), profile, job),
                    context="cover letter (LLM)",
                ) or ""
            except Exception:
                letter_text = ""
        if not letter_text:
            from Pipeline import generate_cover_letter_heuristic
            letter_text = generate_cover_letter_heuristic(profile, job)

        out_dir = ROOT / "vault" / safe_filename(
            f"{job.get('company', 'job')}_{job.get('title', 'cv')}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        letter_path = str(out_dir / "lettre.txt")
        Path(letter_path).write_text(letter_text, encoding="utf-8")

    if cv_path or letter_path:
        db.save_generation(job["id"], cv_path, letter_path)

    return {
        "cv_result": cv_result,
        "cv_path": cv_path,
        "letter_text": letter_text,
        "letter_path": letter_path,
    }


# ─── MODALE STUDIO ───────────────────────────────────────────────
@st.dialog("🎬 Studio de Candidature", width="large")
def studio_dialog(job_id: str):
    job = db.get_job_by_id(job_id)
    if not job:
        st.error("Offre introuvable.")
        return

    # session-state slot pour conserver la dernière génération de cette offre
    state_key = f"gen_state_{job_id}"
    gen_state: dict = st.session_state.get(state_key, {})

    left, right = st.columns([1, 1], gap="large")

    # ── COLONNE GAUCHE : INFOS DE L'OFFRE ────────────────────────
    with left:
        st.markdown(f"### {job['title']}")
        st.markdown(
            f"<div class='row-meta'>🏢 <b>{job.get('company', '?')}</b> · "
            f"📍 {job.get('location', '?')}</div>",
            unsafe_allow_html=True,
        )
        score = int(job.get("fit_score", 0))
        st.markdown(
            f"<div style='margin:12px 0;'>"
            f"<span class='score-pill {score_class(score)}'>{score}% Fit</span> "
            f"<span class='score-pill' style='background:rgba(56,189,248,0.1);"
            f"color:var(--brand);border:1px solid rgba(56,189,248,0.25);'>"
            f"{STATUS_EMOJI.get(job.get('status','new'),'•')} {job.get('status','new')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if job.get("matched_skills"):
            st.caption("Compétences détectées")
            st.write(" · ".join(f"`{s}`" for s in job["matched_skills"][:10]))

        st.caption("Description")
        desc = job.get("description") or "_(pas de description)_"
        st.markdown(
            f"<div style='max-height:280px;overflow-y:auto;padding:12px;"
            f"background:rgba(2,6,23,0.6);border:1px solid var(--border);"
            f"border-radius:12px;font-size:0.88rem;color:var(--text-muted);"
            f"white-space:pre-wrap;'>{desc[:2500]}</div>",
            unsafe_allow_html=True,
        )

        if job.get("url"):
            st.link_button("🌐 Voir l'offre d'origine", job["url"], use_container_width=True)

    # ── COLONNE DROITE : GÉNÉRATION ──────────────────────────────
    with right:
        st.markdown("### ⚙️ Génération")
        gen_cv = st.checkbox("📄 CV PDF (Typst)", value=True, key=f"opt_cv_{job_id}")
        gen_letter = st.checkbox("✉️ Lettre de motivation", value=True, key=f"opt_lt_{job_id}")
        use_llm = st.checkbox("🤖 Lettre IA (Gemini)", value=True, key=f"opt_llm_{job_id}")

        if st.button("🚀 Générer la candidature", type="primary",
                     use_container_width=True, key=f"btn_gen_{job_id}"):
            with st.spinner("Génération en cours..."):
                try:
                    result = generate_documents(
                        job, gen_cv=gen_cv, gen_letter=gen_letter, use_llm=use_llm,
                        headline_override=gen_state.get("edited_headline"),
                        summary_override=gen_state.get("edited_summary"),
                    )
                    gen_state.update(result)
                    cv_data = result.get("cv_result", {}).get("cv_data", {}) or {}
                    gen_state.setdefault("edited_headline", cv_data.get("headline", ""))
                    gen_state.setdefault("edited_summary", cv_data.get("summary", ""))
                    st.session_state[state_key] = gen_state
                    st.success("✅ Documents générés !")
                except Exception as exc:
                    st.error(f"❌ {exc}")

        if gen_state:
            st.divider()
            st.markdown("### ✍️ Édition avant export")

            cv_data = gen_state.get("cv_result", {}).get("cv_data", {}) or {}
            headline_default = gen_state.get("edited_headline", cv_data.get("headline", ""))
            summary_default = gen_state.get("edited_summary", cv_data.get("summary", ""))

            edited_headline = st.text_area(
                "Accroche (Headline)", value=headline_default, height=70,
                key=f"hl_{job_id}",
            )
            edited_summary = st.text_area(
                "Résumé (Summary)", value=summary_default, height=130,
                key=f"sm_{job_id}",
            )
            edited_letter = st.text_area(
                "Lettre de motivation",
                value=gen_state.get("letter_text", ""),
                height=240,
                key=f"lt_{job_id}",
            )
            gen_state["edited_headline"] = edited_headline
            gen_state["edited_summary"] = edited_summary
            gen_state["letter_text"] = edited_letter
            st.session_state[state_key] = gen_state

            # Persiste la lettre éditée sur disque pour que le download soit cohérent
            if gen_state.get("letter_path") and edited_letter:
                try:
                    Path(gen_state["letter_path"]).write_text(edited_letter, encoding="utf-8")
                except Exception:
                    pass

            st.divider()
            st.markdown("### 📥 Téléchargements")
            d1, d2 = st.columns(2)
            with d1:
                cv_path = gen_state.get("cv_path") or ""
                if cv_path and Path(cv_path).exists():
                    ext = Path(cv_path).suffix or ".pdf"
                    mime = "application/pdf" if ext == ".pdf" else "text/plain"
                    with open(cv_path, "rb") as f:
                        st.download_button(
                            "📄 CV", data=f.read(),
                            file_name=f"CV_Zein_{safe_filename(job.get('company',''))}{ext}",
                            mime=mime, use_container_width=True, type="primary",
                            key=f"dl_cv_{job_id}",
                        )
                else:
                    st.info("CV indisponible")
            with d2:
                if edited_letter:
                    st.download_button(
                        "✉️ Lettre",
                        data=edited_letter.encode("utf-8"),
                        file_name=f"Lettre_{safe_filename(job.get('company',''))}.txt",
                        mime="text/plain", use_container_width=True,
                        key=f"dl_lt_{job_id}",
                    )

            st.divider()
            if st.button("✅ J'ai postulé — marquer comme envoyé",
                         type="primary", use_container_width=True,
                         key=f"sent_{job_id}"):
                db.mark_as_sent(
                    job_id=job_id, via="manual",
                    edited_headline=edited_headline,
                    edited_summary=edited_summary,
                    vault_path=gen_state.get("cv_path") or gen_state.get("letter_path"),
                )
                st.session_state.pop(state_key, None)
                st.session_state.pop("studio_open_for", None)
                st.success("Candidature archivée 🎉")
                st.rerun()


# ─── HERO ────────────────────────────────────────────────────────
stats = db.get_stats()

st.markdown(
    """
    <div class="hero-container">
        <div class="hero-h1">Studio de Candidature</div>
        <div class="hero-h2">
            Sélectionne une offre, prépare ta candidature en un clic,
            édite le contenu, télécharge et envoie. Tout sur une seule page.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Offres", stats["total"])
k2.metric("Envoyées", stats["sent"])
k3.metric("Entretiens", stats["interviews"])
k4.metric("Offres reçues", stats["offers"])


# ═══════════════════════════════════════════════════════════════
# SECTION 1 — SMART MATCH
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>① SMART MATCH</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Tes meilleures offres</div>", unsafe_allow_html=True)

filt_c1, filt_c2, filt_c3 = st.columns([1, 1, 2])
with filt_c1:
    min_score = st.slider("Score minimum", 0, 100, 60, step=5)
with filt_c2:
    only_open = st.checkbox("Seulement non traitées", value=True)
with filt_c3:
    search = st.text_input("🔎 Recherche", placeholder="poste, entreprise...")

raw_jobs = db.get_jobs(min_score=min_score, search=search or None, limit=200)
if only_open:
    smart_jobs = [j for j in raw_jobs if j.get("status") in {"new", "selected", "generated"}]
else:
    smart_jobs = raw_jobs
smart_jobs = smart_jobs[:50]

if not smart_jobs:
    st.info("Aucune offre ne correspond à ces filtres.")
else:
    df = pd.DataFrame([
        {
            "Score": int(j.get("fit_score", 0)),
            "Statut": f"{STATUS_EMOJI.get(j.get('status','new'),'•')} {j.get('status','new')}",
            "Poste": j.get("title", ""),
            "Entreprise": j.get("company", ""),
            "Lieu": j.get("location", ""),
            "Source": j.get("source", ""),
            "Lien": j.get("url", "") or None,
        }
        for j in smart_jobs
    ])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        height=min(420, 60 + 36 * len(df)),
        column_config={
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%d%%"
            ),
            "Lien": st.column_config.LinkColumn("Lien", display_text="🌐"),
        },
    )

    st.markdown("#### 🎬 Préparer une candidature")
    st.caption("Une ligne = une offre. Clique pour ouvrir le Studio.")

    for j in smart_jobs[:15]:
        score = int(j.get("fit_score", 0))
        c_info, c_btn = st.columns([5, 1.2])
        with c_info:
            st.markdown(
                f"""
                <div class='row-card'>
                    <div style='display:flex;justify-content:space-between;align-items:center;gap:12px;'>
                        <div>
                            <div class='row-title'>{j.get('title','')}</div>
                            <div class='row-meta'>{j.get('company','?')} — {j.get('location','?')}</div>
                        </div>
                        <span class='score-pill {score_class(score)}'>{score}%</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c_btn:
            if st.button("Préparer la candidature", key=f"prep_{j['id']}",
                         use_container_width=True):
                st.session_state["studio_open_for"] = j["id"]
                st.rerun()

st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SECTION 2 — STUDIO (ouvert via la modale)
# ═══════════════════════════════════════════════════════════════
if st.session_state.get("studio_open_for"):
    studio_dialog(st.session_state["studio_open_for"])


# ═══════════════════════════════════════════════════════════════
# SECTION 3 — ARCHIVES (candidatures envoyées)
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>③ ARCHIVES</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Candidatures envoyées</div>", unsafe_allow_html=True)

sent_jobs = db.get_jobs(status="sent", limit=200)

if not sent_jobs:
    st.info("Aucune candidature envoyée pour le moment. Prépare et envoie ta première via le Studio ci-dessus.")
else:
    st.caption(f"{len(sent_jobs)} candidature(s) envoyée(s)")
    for j in sent_jobs:
        with st.container():
            top, actions = st.columns([4, 2])
            with top:
                sent_at = j.get("sent_at") or j.get("applied_date") or "—"
                st.markdown(
                    f"""
                    <div class='row-card'>
                        <div class='row-title'>{j.get('title','')}</div>
                        <div class='row-meta'>
                            🏢 {j.get('company','?')} — 📍 {j.get('location','?')}
                            &nbsp;·&nbsp; 📤 Envoyé le <b>{sent_at}</b>
                            &nbsp;·&nbsp; via <b>{j.get('sent_via') or 'manual'}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with actions:
                a1, a2 = st.columns(2)
                cv_path = j.get("cv_path") or j.get("vault_path") or ""
                letter_path = j.get("letter_path") or ""
                with a1:
                    if cv_path and Path(cv_path).exists():
                        ext = Path(cv_path).suffix or ".pdf"
                        mime = "application/pdf" if ext == ".pdf" else "text/plain"
                        with open(cv_path, "rb") as f:
                            st.download_button(
                                "📄 CV", data=f.read(),
                                file_name=f"CV_{safe_filename(j.get('company',''))}{ext}",
                                mime=mime, use_container_width=True,
                                key=f"arch_cv_{j['id']}",
                            )
                    else:
                        st.button("📄 CV", disabled=True, use_container_width=True,
                                  key=f"arch_cv_na_{j['id']}")
                with a2:
                    if letter_path and Path(letter_path).exists():
                        with open(letter_path, "rb") as f:
                            st.download_button(
                                "✉️ Lettre", data=f.read(),
                                file_name=f"Lettre_{safe_filename(j.get('company',''))}.txt",
                                mime="text/plain", use_container_width=True,
                                key=f"arch_lt_{j['id']}",
                            )
                    else:
                        st.button("✉️ Lettre", disabled=True, use_container_width=True,
                                  key=f"arch_lt_na_{j['id']}")

st.markdown("</div>", unsafe_allow_html=True)

st.caption("© Job Copilot · Studio de Candidature · Zein ELAJAMY — ENSEM 2026")
