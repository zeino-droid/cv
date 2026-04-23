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


def smart_keywords_from_profile(profile: dict, max_kw: int = 8) -> list[str]:
    """Construit une liste de mots-clés intelligents à partir du profil."""
    keywords: list[str] = []

    # 1. Titres de poste passés (les plus pertinents)
    for exp in profile.get("experience_stark", [])[:3]:
        title = (exp.get("title") or "").strip()
        if title and len(title) < 80 and title not in keywords:
            # On garde les titres "ingénieur ..." courts
            short = title.split(":")[0].strip()
            if short and short not in keywords:
                keywords.append(short)

    # 2. Combinaisons "Ingénieur + hard skill"
    taxonomy = profile.get("skills_taxonomy", {})
    for skill in taxonomy.get("hard_skills", [])[:5]:
        name = (skill.get("name") or "").strip()
        if name:
            kw = f"Ingénieur {name}"
            if kw not in keywords:
                keywords.append(kw)

    # 3. Domaines d'expertise
    for domain in taxonomy.get("domain_knowledge", [])[:3]:
        kw = f"Ingénieur {domain.split('(')[0].strip()}"
        if kw not in keywords:
            keywords.append(kw)

    return keywords[:max_kw]


def google_fallback_url(company: str, title: str) -> str:
    """URL de secours : recherche Google 'entreprise carrières titre'."""
    query = f"{(company or '').strip()} carrières {(title or '').strip()}".strip()
    return "https://www.google.com/search?q=" + query.replace(" ", "+")


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

    if gen_cv and cv_path:
        try:
            db.save_resume_version(
                job_id=job["id"],
                headline=headline_override or "",
                summary=summary_override or "",
                cv_path=cv_path,
                is_final=False,
                notes="Auto-saved on generation",
            )
        except Exception:
            pass
    if gen_letter and letter_text:
        try:
            db.save_cover_letter_version(
                job_id=job["id"],
                letter_text=letter_text,
                letter_path=letter_path,
                is_final=False,
                notes="Auto-saved on generation",
            )
        except Exception:
            pass

    return {
        "cv_result": cv_result,
        "cv_path": cv_path,
        "letter_text": letter_text,
        "letter_path": letter_path,
    }


# ─── COPILOTE IA : réécriture ciblée via le LLM existant ─────────
def _copilot_rewrite(target: str, command: str, current_summary: str,
                     current_letter: str, job: dict, profile: dict) -> str | None:
    """Appelle le LLM (Gemini via cv_generator) pour réécrire un texte ciblé."""
    if target == "Résumé CV":
        current_text = current_summary or ""
        context_hint = "résumé de CV (3-4 lignes max, orienté ATS, en français)"
    elif target == "Introduction lettre uniquement":
        chunks = (current_letter or "").split("\n\n")
        current_text = chunks[2] if len(chunks) > 2 else (current_letter or "")[:500]
        context_hint = "premier paragraphe d'une lettre de motivation (en français)"
    else:
        current_text = current_letter or ""
        context_hint = "lettre de motivation complète (en français)"

    prompt = f"""Tu es un expert en rédaction de candidatures pour ingénieurs en France.

TEXTE ACTUEL ({context_hint}) :
{current_text}

POSTE CIBLÉ : {job.get('title','')} chez {job.get('company','')}
LIEU : {job.get('location','')}
COMPÉTENCES CLÉ : {', '.join((job.get('matched_skills') or [])[:6])}

INSTRUCTION DE L'UTILISATEUR : {command}

RÈGLES STRICTES :
- Garde la même structure si l'utilisateur ne précise pas autrement
- Reste professionnel et naturel, en français
- N'ajoute AUCUN préambule type "Voici le texte réécrit :"
- Réponds UNIQUEMENT avec le texte réécrit, rien d'autre
"""

    async def _call_llm():
        try:
            from engine.cv_generator import PersonalCVGenerator
            gen = PersonalCVGenerator()
            if getattr(gen, "llm", None) is None:
                return None
            return await gen.llm.generate(prompt, temperature=0.4)
        except Exception as exc:
            st.error(f"Erreur LLM : {exc}")
            return None

    result = run_coroutine_sync(_call_llm(), context="copilot rewrite")
    if isinstance(result, str):
        return result.strip()
    return None


# ─── MODALE STUDIO ───────────────────────────────────────────────
@st.dialog("🎬 Studio de Candidature", width="large")
def studio_dialog(job_id: str):
    job = db.get_job_by_id(job_id)
    if not job:
        st.error("Offre introuvable.")
        return

    profile = load_profile()
    state_key = f"gen_state_{job_id}"
    gen_state: dict = st.session_state.get(state_key, {})

    # ── HEADER COMPACT ──────────────────────────────────────────
    score = int(job.get("fit_score", 0))
    st.markdown(
        f"### {job['title']} "
        f"<span style='font-size:0.85rem;color:#94a3b8;font-weight:500;'>"
        f"— {job.get('company','?')} · 📍 {job.get('location','?')}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='margin:6px 0 12px 0;'>"
        f"<span class='score-pill {score_class(score)}'>{score}% Fit</span> "
        f"<span class='score-pill' style='background:rgba(56,189,248,0.1);"
        f"color:var(--brand);border:1px solid rgba(56,189,248,0.25);'>"
        f"{STATUS_EMOJI.get(job.get('status','new'),'•')} {job.get('status','new')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Pré-remplit la lettre par défaut (heuristique, rapide, sans LLM)
    if "letter_text" not in gen_state or not gen_state.get("letter_text"):
        try:
            from Pipeline import generate_cover_letter_heuristic
            gen_state["letter_text"] = generate_cover_letter_heuristic(profile, job)
            st.session_state[state_key] = gen_state
        except Exception:
            gen_state.setdefault("letter_text", "")

    # Pré-remplit le résumé par défaut depuis le profil
    if "edited_summary" not in gen_state or not gen_state.get("edited_summary"):
        default_summary = (
            (profile.get("personal_info") or {}).get("summary_default")
            or (profile.get("personal_info") or {}).get("summary")
            or "Ingénieur R&D — modélisation, simulation et data engineering."
        )
        gen_state["edited_summary"] = default_summary
        st.session_state[state_key] = gen_state

    # ── 2 ONGLETS ───────────────────────────────────────────────
    tab_analyse, tab_studio = st.tabs(
        ["🔬 Analyse", "🎬 Studio CV + Lettre"]
    )

    # === ONGLET 1 : ANALYSE =====================================
    with tab_analyse:
        from engine.studio_analysis import build_skill_matrix, render_heatmap_html
        matrix = build_skill_matrix(profile, job)
        st.components.v1.html(render_heatmap_html(matrix), height=520, scrolling=True)

        if matrix["missing"]:
            top = ", ".join(matrix["missing"][:3])
            st.info(
                f"💡 **Conseil ATS** : mentionne explicitement **{top}** "
                f"dans ton résumé ou ta lettre pour booster le score."
            )

        with st.expander("📄 Description complète de l'offre"):
            desc = job.get("description") or "_(pas de description)_"
            st.markdown(
                f"<div style='max-height:240px;overflow-y:auto;padding:10px;"
                f"font-size:0.85rem;color:var(--text-muted);white-space:pre-wrap;'>"
                f"{desc[:3000]}</div>",
                unsafe_allow_html=True,
            )

        lc1, lc2 = st.columns(2)
        with lc1:
            if job.get("url"):
                st.link_button("🌐 Voir l'offre d'origine", job["url"],
                               use_container_width=True)
            else:
                st.button("🌐 Voir l'offre d'origine", disabled=True,
                          use_container_width=True, key=f"no_url_{job['id']}")
        with lc2:
            st.link_button(
                "🔍 Chercher sur Google",
                google_fallback_url(job.get("company", ""), job.get("title", "")),
                use_container_width=True,
                help="Lien de secours si l'offre d'origine a expiré",
            )

    # === ONGLET 2 : STUDIO UNIFIÉ (Génération + Édition + Copilote + PDF live) ===
    with tab_studio:
        already_generated = bool(gen_state.get("cv_path")) or bool(
            gen_state.get("studio_initialized")
        )

        # ─── PHASE 1 : génération initiale via Gemini ──────────
        if not already_generated:
            st.markdown(
                "<div style='background:rgba(56,189,248,0.08);border:1px solid "
                "rgba(56,189,248,0.25);border-radius:8px;padding:14px;"
                "color:#e2e8f0;font-size:0.92rem;line-height:1.55;'>"
                "<strong>🧠 Génération intelligente.</strong> "
                "Gemini va lire ton profil complet et l'offre ciblée, puis "
                "rédiger un CV professionnel et une lettre personnalisée. "
                "Tu pourras ensuite tout éditer ou demander des retouches au copilote."
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("&nbsp;")
            if st.button("🚀 Générer le CV + Lettre avec Gemini",
                         type="primary", use_container_width=True,
                         key=f"btn_studio_gen_{job_id}"):
                with st.spinner("Gemini rédige ton CV et ta lettre..."):
                    try:
                        result = generate_documents(
                            job, gen_cv=True, gen_letter=True, use_llm=True,
                            headline_override=gen_state.get("edited_headline"),
                            summary_override=gen_state.get("edited_summary"),
                        )
                        gen_state.update(result)
                        if result.get("letter_text"):
                            gen_state["letter_text"] = result["letter_text"]
                        # Récupère headline/summary réellement utilisés par le générateur
                        cv_res = result.get("cv_result") or {}
                        if cv_res.get("headline"):
                            gen_state["edited_headline"] = cv_res["headline"]
                        if cv_res.get("summary"):
                            gen_state["edited_summary"] = cv_res["summary"]
                        gen_state["studio_initialized"] = True
                        st.session_state[state_key] = gen_state
                        st.success("✅ Génération terminée. Aperçu PDF disponible ci-dessous.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Erreur Gemini : {exc}")
                        st.caption("Vérifie que la clé `GEMINI_API_KEY` est bien configurée.")

        # ─── PHASE 2 : aperçu PDF + édition + copilote ─────────
        else:
            preview_col, edit_col = st.columns([1, 1], gap="medium")

            # ───── COLONNE GAUCHE : APERÇU PDF ─────────────────
            with preview_col:
                st.markdown("##### 📄 Aperçu PDF live")
                cv_preview = gen_state.get("cv_path") or ""
                if cv_preview and Path(cv_preview).exists() and cv_preview.endswith(".pdf"):
                    try:
                        import pypdfium2 as _pdfium
                        pdf_doc = _pdfium.PdfDocument(cv_preview)
                        for i, page in enumerate(pdf_doc):
                            pil_img = page.render(scale=2.0).to_pil()
                            st.image(pil_img, use_container_width=True,
                                     caption=f"Page {i+1}")
                            page.close()
                        pdf_doc.close()
                    except Exception as exc:
                        st.error(f"Erreur rendu PDF : {exc}")
                        with open(cv_preview, "rb") as f:
                            st.download_button(
                                "📄 Télécharger le PDF",
                                data=f.read(),
                                file_name=Path(cv_preview).name,
                                mime="application/pdf",
                                key=f"dl_fb_{job_id}",
                            )
                else:
                    st.warning(
                        "PDF non disponible. Le moteur Typst n'a pas pu générer le rendu. "
                        "Clique sur **Recompiler PDF** ci-dessous."
                    )

                if st.button("🔄 Recompiler PDF avec mes éditions",
                             use_container_width=True,
                             key=f"recomp_{job_id}"):
                    with st.spinner("Recompilation..."):
                        try:
                            result = generate_documents(
                                job, gen_cv=True, gen_letter=False, use_llm=False,
                                headline_override=gen_state.get("edited_headline"),
                                summary_override=gen_state.get("edited_summary"),
                            )
                            gen_state["cv_path"] = result.get("cv_path", "")
                            st.session_state[state_key] = gen_state
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

            # ───── COLONNE DROITE : ÉDITION + COPILOTE ─────────
            with edit_col:
                st.markdown("##### ✏️ Édition manuelle")
                edited_headline = st.text_area(
                    "Accroche",
                    value=gen_state.get("edited_headline", ""),
                    height=70, key=f"hl_{job_id}",
                    placeholder="Ex: Ingénieur R&D · Python · Simulation thermomécanique",
                )
                gen_state["edited_headline"] = edited_headline

                edited_summary = st.text_area(
                    "Résumé professionnel",
                    value=gen_state.get("edited_summary", ""),
                    height=140, key=f"sm_{job_id}",
                )
                gen_state["edited_summary"] = edited_summary
                cnt = len(edited_summary)
                color = "#4ade80" if cnt <= 400 else "#f87171"
                st.markdown(
                    f"<span style='font-size:0.72rem;color:{color};'>"
                    f"{cnt}/400 caractères recommandés</span>",
                    unsafe_allow_html=True,
                )

                edited_letter = st.text_area(
                    "Lettre de motivation",
                    value=gen_state.get("letter_text", ""),
                    height=240, key=f"lt_{job_id}",
                )
                gen_state["letter_text"] = edited_letter
                st.session_state[state_key] = gen_state

                st.markdown("---")
                st.markdown("##### 🤖 Copilote IA")
                st.caption(
                    "Demande des retouches ciblées. "
                    "Ex : *Rends l'intro plus orientée résultats* · "
                    "*Ajoute une mention CFD* · *Raccourcis la lettre*"
                )
                cop_target = st.radio(
                    "Cible",
                    ["Résumé CV", "Lettre complète", "Introduction lettre uniquement"],
                    horizontal=True, key=f"cop_target_{job_id}",
                )
                cop_cmd = st.text_input(
                    "Instruction",
                    placeholder="Ex: Reformule en orienté impact business",
                    key=f"cop_cmd_{job_id}",
                )
                if st.button("⚡ Appliquer", type="primary",
                             use_container_width=True,
                             key=f"cop_run_{job_id}"):
                    if not cop_cmd.strip():
                        st.warning("Tape une instruction d'abord.")
                    else:
                        with st.spinner("Le copilote réécrit..."):
                            rewritten = _copilot_rewrite(
                                target=cop_target, command=cop_cmd,
                                current_summary=gen_state.get("edited_summary", ""),
                                current_letter=gen_state.get("letter_text", ""),
                                job=job, profile=profile,
                            )
                        if rewritten:
                            if cop_target == "Résumé CV":
                                gen_state["edited_summary"] = rewritten
                            else:
                                gen_state["letter_text"] = rewritten
                            st.session_state[state_key] = gen_state
                            st.success("✅ Texte mis à jour. Pense à recompiler le PDF.")
                            st.rerun()
                        else:
                            st.error("Le copilote n'a rien renvoyé (clé API manquante ?).")

            # ───── BLOC VALIDATION & EXPORT ────────────────────
            st.markdown("---")
            st.markdown("#### ✅ Valider & Exporter")
            v1, v2, v3 = st.columns(3)
            with v1:
                cv_path_dl = gen_state.get("cv_path") or ""
                if cv_path_dl and Path(cv_path_dl).exists() and cv_path_dl.endswith(".pdf"):
                    with open(cv_path_dl, "rb") as f:
                        st.download_button(
                            "📄 Télécharger CV (PDF)", data=f.read(),
                            file_name=f"CV_{safe_filename(job.get('company','job'))}.pdf",
                            mime="application/pdf",
                            use_container_width=True, type="primary",
                            key=f"dl_cv_{job_id}",
                        )
                else:
                    st.button("📄 CV PDF indisponible", disabled=True,
                              use_container_width=True,
                              key=f"dl_cv_dis_{job_id}")
            with v2:
                if gen_state.get("letter_text"):
                    st.download_button(
                        "✉️ Télécharger lettre (.txt)",
                        data=gen_state["letter_text"].encode("utf-8"),
                        file_name=f"Lettre_{safe_filename(job.get('company','job'))}.txt",
                        mime="text/plain", use_container_width=True,
                        key=f"dl_lt_{job_id}",
                    )
                else:
                    st.button("✉️ Lettre vide", disabled=True,
                              use_container_width=True,
                              key=f"dl_lt_dis_{job_id}")
            with v3:
                if st.button("⭐ Valider comme version finale",
                             use_container_width=True,
                             key=f"final_{job_id}"):
                    try:
                        # On recompile une dernière fois avec les éditions
                        result = generate_documents(
                            job, gen_cv=True, gen_letter=False, use_llm=False,
                            headline_override=gen_state.get("edited_headline"),
                            summary_override=gen_state.get("edited_summary"),
                        )
                        gen_state["cv_path"] = result.get("cv_path", "") or gen_state.get("cv_path", "")
                        # Persiste la lettre éditée
                        if gen_state.get("letter_text"):
                            out_dir = ROOT / "vault" / safe_filename(
                                f"{job.get('company','job')}_{job.get('title','cv')}"
                            )
                            out_dir.mkdir(parents=True, exist_ok=True)
                            lp = out_dir / "lettre.txt"
                            lp.write_text(gen_state["letter_text"], encoding="utf-8")
                            gen_state["letter_path"] = str(lp)
                        # Sauvegarde versions finales
                        db.save_resume_version(
                            job_id=job_id,
                            headline=gen_state.get("edited_headline", ""),
                            summary=gen_state.get("edited_summary", ""),
                            cv_path=gen_state.get("cv_path", ""),
                            is_final=True,
                            notes="Validée finale par l'utilisateur",
                        )
                        if gen_state.get("letter_text"):
                            db.save_cover_letter_version(
                                job_id=job_id,
                                letter_text=gen_state.get("letter_text", ""),
                                letter_path=gen_state.get("letter_path", ""),
                                is_final=True,
                                notes="Validée finale par l'utilisateur",
                            )
                        st.session_state[state_key] = gen_state
                        st.success("⭐ Version finale archivée.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Erreur : {exc}")

            # ───── MARQUER COMME ENVOYÉ ────────────────────────
            if st.button("📤 J'ai postulé — clore la candidature",
                         type="secondary", use_container_width=True,
                         key=f"sent_{job_id}"):
                db.mark_as_sent(
                    job_id=job_id, via="manual",
                    edited_headline=gen_state.get("edited_headline", ""),
                    edited_summary=gen_state.get("edited_summary", ""),
                    vault_path=gen_state.get("cv_path") or gen_state.get("letter_path"),
                )
                st.session_state.pop(state_key, None)
                st.session_state.pop("studio_open_for", None)
                st.success("Candidature archivée 🎉")
                st.rerun()

            # ───── HISTORIQUE DES VERSIONS ─────────────────────
            with st.expander("🗂 Historique des versions"):
                cv_vers = db.get_resume_versions(job_id)
                lt_vers = db.get_cover_letter_versions(job_id)
                hva, hvb = st.columns(2)
                with hva:
                    st.markdown("**CV**")
                    if not cv_vers:
                        st.caption("Aucune version sauvegardée.")
                    for v in cv_vers[:8]:
                        flag = " ⭐" if v.get("is_final") else ""
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:#94a3b8;'>"
                            f"v{v['version']}{flag} · {v.get('created_at','')[:16]}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                with hvb:
                    st.markdown("**Lettre**")
                    if not lt_vers:
                        st.caption("Aucune version sauvegardée.")
                    for v in lt_vers[:8]:
                        flag = " ⭐" if v.get("is_final") else ""
                        st.markdown(
                            f"<div style='font-size:0.78rem;color:#94a3b8;'>"
                            f"v{v['version']}{flag} · {v.get('created_at','')[:16]}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )


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
# SECTION 0 — RECHERCHE AUTOMATIQUE & AJOUT MANUEL
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>⓪ ALIMENTATION DU PIPELINE</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Trouver de nouvelles offres</div>", unsafe_allow_html=True)

tab_auto, tab_manual = st.tabs(["🤖 Recherche automatique", "✍️ Ajouter une offre manuellement"])

# ─── TAB 1 : RECHERCHE AUTOMATIQUE ──────────────────────────────
with tab_auto:
    profile_data = load_profile()
    profile_kw = smart_keywords_from_profile(profile_data)

    try:
        import yaml as _yaml
        _cfg = _yaml.safe_load(open(ROOT / "profiles" / "search_config.yaml", encoding="utf-8")) or {}
    except Exception:
        _cfg = {}
    cfg_locations = (_cfg.get("search", {}) or {}).get("locations") or [
        "Paris, France", "Lyon, France", "Toulouse, France", "France",
    ]
    cfg_sites = (_cfg.get("search", {}) or {}).get("sites") or ["google", "glassdoor"]

    mode = st.radio(
        "Stratégie de recherche",
        ["🧠 Selon mon profil (auto)", "📝 Mots-clés personnalisés"],
        horizontal=True,
        key="auto_mode",
    )

    if mode.startswith("🧠"):
        st.caption(
            "Mots-clés générés à partir de ton profil "
            "(titres de poste passés + hard skills + domaines d'expertise)."
        )
        kw_text = st.text_area(
            "Mots-clés (modifiables, un par ligne)",
            value="\n".join(profile_kw),
            height=180,
            key="auto_kw_profile",
        )
    else:
        st.caption("Saisis tes propres mots-clés (un par ligne).")
        kw_text = st.text_area(
            "Mots-clés (un par ligne)",
            value="Ingénieur R&D simulation\nIngénieur CFD\nIngénieur thermique",
            height=180,
            key="auto_kw_custom",
        )

    sc1, sc2 = st.columns([3, 1])
    with sc1:
        sel_locations = st.multiselect(
            "📍 Zones géographiques", options=cfg_locations,
            default=cfg_locations[:4], key="auto_locs",
        )
    with sc2:
        results_per_q = st.number_input(
            "Résultats / requête", min_value=5, max_value=50, value=15, step=5,
            key="auto_npq",
        )

    st.markdown("##### 🧠 Moteur avancé")
    ai1, ai2, ai3, ai4 = st.columns(4)
    with ai1:
        use_expansion = st.toggle(
            "💡 Expansion sémantique", value=True, key="ai_exp",
            help="Gemini génère des variantes pertinentes de tes mots-clés (synonymes, intitulés équivalents).",
        )
    with ai2:
        use_rerank = st.toggle(
            "🧠 Re-classement IA", value=True, key="ai_rerank",
            help="Gemini évalue le fit profond de chaque top candidat (score + raisonnement).",
        )
    with ai3:
        use_skills = st.toggle(
            "🔍 Extraction compétences", value=True, key="ai_skills",
            help="Gemini extrait les vraies compétences requises depuis chaque description.",
        )
    with ai4:
        use_remotive = st.toggle(
            "🌐 Source bonus Remotive", value=True, key="ai_remotive",
            help="Ajoute Remotive (offres tech ouvertes au remote France) en complément.",
        )

    st.caption(
        "Sources actives : **Google Jobs · Glassdoor · ZipRecruiter** (+ Remotive si activé). "
        "LinkedIn et Indeed sont définitivement exclus — leurs liens expirent et cassent le pipeline."
    )

    import threading
    import time as _time

    # ─── Pattern asynchrone pour permettre la pause/arrêt en cours ────
    if "search_state" not in st.session_state:
        st.session_state["search_state"] = "idle"  # idle | running | done

    search_state = st.session_state["search_state"]

    if search_state == "idle":
        launch = st.button(
            "🚀 Lancer la recherche avancée", type="primary",
            use_container_width=True, key="btn_auto_scan",
        )
        if launch:
            keywords = [k.strip() for k in kw_text.splitlines() if k.strip()]
            if not keywords or not sel_locations:
                st.warning("Indique au moins un mot-clé et une zone géographique.")
            else:
                from engine.sourcing_advanced import scan_advanced

                stop_event = threading.Event()
                progress_box = {"p": 0.0, "msg": "Initialisation…"}

                def _cb(p: float, msg: str):
                    progress_box["p"] = min(max(p, 0.0), 1.0)
                    progress_box["msg"] = msg

                def _runner():
                    try:
                        return scan_advanced(
                            keywords=keywords,
                            locations=sel_locations,
                            sites=["google", "glassdoor", "zip_recruiter"],
                            results_per_query=int(results_per_q),
                            use_llm_expansion=use_expansion,
                            use_llm_rerank=use_rerank,
                            use_llm_skills=use_skills,
                            use_remotive=use_remotive,
                            progress_callback=_cb,
                            should_stop=stop_event.is_set,
                        )
                    except Exception as exc:
                        return ("__error__", str(exc))

                executor = ThreadPoolExecutor(max_workers=1)
                future = executor.submit(_runner)

                st.session_state["search_state"] = "running"
                st.session_state["search_future"] = future
                st.session_state["search_executor"] = executor
                st.session_state["search_stop_event"] = stop_event
                st.session_state["search_progress"] = progress_box
                st.rerun()

    if st.session_state.get("search_state") == "running":
        future = st.session_state.get("search_future")
        stop_event = st.session_state.get("search_stop_event")
        progress_box = st.session_state.get("search_progress", {"p": 0.0, "msg": "…"})

        progress_bar = st.progress(progress_box["p"], text=progress_box["msg"])

        bcol1, bcol2 = st.columns([1, 1])
        with bcol1:
            if st.button("⏸️ Pause / Arrêter la recherche", type="secondary",
                         use_container_width=True, key="btn_stop_search"):
                if stop_event:
                    stop_event.set()
                st.toast("⏸️ Arrêt demandé… les offres collectées seront conservées.")
        with bcol2:
            st.caption("La recherche tourne en arrière-plan. Tu peux l'arrêter à tout moment.")

        # Polling : si pas terminée, on attend un peu et on rerun
        if future is not None and future.done():
            try:
                result = future.result()
            except Exception as exc:
                result = ("__error__", str(exc))

            executor = st.session_state.get("search_executor")
            if executor:
                try: executor.shutdown(wait=False)
                except Exception: pass

            for k in ("search_future", "search_executor", "search_stop_event", "search_progress"):
                st.session_state.pop(k, None)

            if isinstance(result, tuple) and len(result) > 0 and result[0] == "__error__":
                st.error(f"❌ Erreur durant la recherche : {result[1]}")
                st.session_state["search_state"] = "idle"
            else:
                added = db.upsert_jobs(result)
                stopped = stop_event and stop_event.is_set()
                if stopped:
                    st.warning(
                        f"⏸️ Recherche interrompue : {len(result)} offres collectées avant l'arrêt · "
                        f"**{added} nouvelles** ajoutées au pipeline."
                    )
                else:
                    st.success(
                        f"✅ Recherche terminée : {len(result)} offres analysées · "
                        f"**{added} nouvelles** ajoutées au pipeline."
                    )
                st.session_state["search_state"] = "idle"
            st.rerun()
        else:
            _time.sleep(0.8)
            st.rerun()

# ─── TAB 2 : AJOUT MANUEL ───────────────────────────────────────
with tab_manual:
    st.caption(
        "Tu as repéré une offre intéressante hors scraping ? "
        "Ajoute-la ici et elle rejoindra le pipeline pour génération CV/lettre + suivi."
    )
    with st.form("manual_add_form", clear_on_submit=True):
        m1, m2 = st.columns(2)
        with m1:
            m_title = st.text_input("Intitulé du poste *", placeholder="Ingénieur R&D Simulation")
            m_company = st.text_input("Entreprise *", placeholder="Airbus")
            m_location = st.text_input("Lieu", placeholder="Toulouse, France")
        with m2:
            m_url = st.text_input("URL de l'offre", placeholder="https://...")
            m_source = st.text_input("Source", value="manual")
            m_score = st.slider("Score initial estimé", 0, 100, 70, step=5)

        m_desc = st.text_area(
            "Description / annonce complète", height=180,
            placeholder="Colle ici la description complète de l'offre — elle sera utilisée pour générer le CV et la lettre.",
        )

        submitted = st.form_submit_button(
            "➕ Ajouter au pipeline et préparer", type="primary",
            use_container_width=True,
        )

        if submitted:
            if not m_title or not m_company:
                st.warning("Le titre et l'entreprise sont obligatoires.")
            else:
                from datetime import date as _date
                manual_id = f"MAN-{abs(hash(m_title + m_company + m_url))}"
                manual_job = {
                    "id": manual_id,
                    "title": m_title.strip(),
                    "company": m_company.strip(),
                    "location": m_location.strip() or "France",
                    "description": m_desc.strip(),
                    "url": m_url.strip(),
                    "source": m_source.strip() or "manual",
                    "fit_score": int(m_score),
                    "matched_skills": [],
                    "required_skills": [],
                    "sourcing_date": _date.today().isoformat(),
                }
                db.upsert_jobs([manual_job])
                st.success(f"✅ Offre ajoutée : {m_title} chez {m_company}")
                st.session_state["studio_open_for"] = manual_id
                st.rerun()

st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SECTION 1 — SMART MATCH
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>① SMART MATCH</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Tes meilleures offres</div>", unsafe_allow_html=True)

all_jobs_for_filters = db.get_jobs(limit=1000)
locations = sorted({(j.get("location") or "").strip() for j in all_jobs_for_filters if j.get("location")})
all_sources = sorted({(j.get("source") or "").strip().lower() for j in all_jobs_for_filters if j.get("source")})
sourcing_dates = [j.get("sourcing_date") for j in all_jobs_for_filters if j.get("sourcing_date")]

# Sources réputées fiables (liens qui n'expirent pas) → cochées par défaut
RELIABLE_SOURCES = {"google", "glassdoor", "zip_recruiter", "remotive", "manual"}
default_sources = [s for s in all_sources if s in RELIABLE_SOURCES] or all_sources

def _parse_date(value: str):
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except Exception:
        return None

parsed_dates = [d for d in (_parse_date(s) for s in sourcing_dates) if d]
min_d = min(parsed_dates) if parsed_dates else datetime.today().date()
max_d = max(parsed_dates) if parsed_dates else datetime.today().date()

f1, f2, f3, f4 = st.columns([2, 1.4, 1.6, 1])
with f1:
    search = st.text_input("🔎 Recherche", placeholder="poste, entreprise...")
with f2:
    city_filter = st.selectbox("📍 Ville", ["Toutes"] + locations, index=0)
with f3:
    if min_d == max_d:
        date_range = st.date_input("📅 Découverte (depuis)", value=min_d)
        date_from, date_to = date_range, max_d
    else:
        date_range = st.date_input(
            "📅 Période de découverte",
            value=(min_d, max_d), min_value=min_d, max_value=max_d,
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            date_from, date_to = date_range
        else:
            date_from, date_to = min_d, max_d
with f4:
    min_score = st.slider("Score min", 0, 100, 60, step=5)

cb1, cb2 = st.columns([2, 3])
with cb1:
    only_open = st.checkbox("Uniquement les offres non traitées", value=True)
with cb2:
    selected_sources = st.multiselect(
        "🔗 Sources",
        options=all_sources,
        default=default_sources,
        help="Filtre par source d'origine. Toutes les sources affichées ici ont des liens stables.",
    )

raw_jobs = db.get_jobs(
    min_score=min_score,
    search=search or None,
    location_filter=city_filter if city_filter != "Toutes" else None,
    limit=500,
)

def _within_range(job: dict) -> bool:
    d = _parse_date(job.get("sourcing_date") or "")
    if d is None:
        return True
    return date_from <= d <= date_to

raw_jobs = [j for j in raw_jobs if _within_range(j)]
if selected_sources:
    sel = {s.lower() for s in selected_sources}
    raw_jobs = [j for j in raw_jobs if (j.get("source") or "").lower() in sel]
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
            "Découverte": (j.get("sourcing_date") or "")[:10],
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
        sourcing = (j.get("sourcing_date") or "")[:10] or "—"
        ai_score = j.get("ai_score")
        ai_reason = (j.get("ai_reason") or "").strip()
        ai_badge = (
            f"&nbsp;·&nbsp; 🧠 IA <b>{int(ai_score)}%</b>" if ai_score is not None else ""
        )
        ai_line = (
            f"<div class='row-meta' style='margin-top:4px;font-style:italic;opacity:0.85;'>💬 {ai_reason}</div>"
            if ai_reason else ""
        )
        c_info, c_btn, c_del = st.columns([5, 1.2, 0.8])
        with c_info:
            st.markdown(
                f"""
                <div class='row-card'>
                    <div style='display:flex;justify-content:space-between;align-items:center;gap:12px;'>
                        <div style='flex:1;'>
                            <div class='row-title'>{j.get('title','')}</div>
                            <div class='row-meta'>
                                {j.get('company','?')} — {j.get('location','?')}
                                &nbsp;·&nbsp; 📅 <b>{sourcing}</b>
                                {ai_badge}
                            </div>
                            {ai_line}
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
        with c_del:
            if st.button("🗑️", key=f"del_{j['id']}",
                         use_container_width=True, help="Supprimer définitivement"):
                db.delete_job(j["id"])
                st.toast(f"Offre supprimée : {j.get('title','')[:40]}")
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
            top, actions = st.columns([4, 2.5])
            with top:
                sourcing = (j.get("sourcing_date") or "")[:10] or "—"
                sent_at = j.get("sent_at") or j.get("applied_date") or "—"
                st.markdown(
                    f"""
                    <div class='row-card'>
                        <div class='row-title'>{j.get('title','')}</div>
                        <div class='row-meta'>
                            🏢 {j.get('company','?')} — 📍 {j.get('location','?')}<br/>
                            📅 Découverte le <b>{sourcing}</b>
                            &nbsp;·&nbsp; 📤 Envoyé le <b>{sent_at}</b>
                            &nbsp;·&nbsp; via <b>{j.get('sent_via') or 'manual'}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with actions:
                a1, a2, a3 = st.columns([1, 1, 0.7])
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
                with a3:
                    with st.popover("🗑️", use_container_width=True,
                                    help="Supprimer ou remettre en préparation"):
                        st.markdown(f"**{j.get('title','')[:60]}**")
                        st.caption("Que veux-tu faire de cette candidature ?")
                        if st.button("↩️ Remettre dans « Préparer »",
                                     key=f"arch_reset_{j['id']}",
                                     use_container_width=True):
                            db.update_status(j["id"], "new", j.get("notes") or "")
                            st.toast("Offre remise en préparation 🎯")
                            st.rerun()
                        if st.button("❌ Supprimer définitivement",
                                     key=f"arch_kill_{j['id']}",
                                     type="primary",
                                     use_container_width=True):
                            db.delete_job(j["id"])
                            st.toast(f"Candidature supprimée : {j.get('title','')[:40]}")
                            st.rerun()

st.markdown("</div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SECTION 4 — PROFIL (édition visuelle de master_profile.json)
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>④ PROFIL</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Édite ton profil maître</div>", unsafe_allow_html=True)
st.caption(
    "Toutes les modifications sont sauvegardées dans `profiles/master_profile.json` "
    "et utilisées immédiatement par le moteur de génération de CV/lettre."
)

PROFILE_PATH = Path("profiles/master_profile.json")


def _load_profile() -> dict:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_profile(data: dict) -> None:
    PROFILE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


prof = _load_profile()
pi = prof.setdefault("personal_info", {})

p_tab1, p_tab2, p_tab3, p_tab4, p_tab5 = st.tabs([
    "👤 Identité", "🎓 Formation", "💼 Expériences",
    "🛠️ Compétences", "📦 JSON brut",
])

# ─── IDENTITÉ ───────────────────────────────────────────────────
with p_tab1:
    with st.form("form_identity", clear_on_submit=False):
        i1, i2 = st.columns(2)
        with i1:
            n_name = st.text_input("Nom complet", value=pi.get("name", ""))
            n_email = st.text_input("Email", value=pi.get("email", ""))
            n_phone = st.text_input("Téléphone", value=pi.get("phone", ""))
            n_location = st.text_input("Localisation", value=pi.get("location", ""))
        with i2:
            n_linkedin = st.text_input("LinkedIn", value=pi.get("linkedin", ""))
            n_github = st.text_input("GitHub", value=pi.get("github", ""))
            n_hobbies = st.text_input(
                "Loisirs (séparés par virgules)",
                value=", ".join(pi.get("hobbies", [])),
            )

        n_headline = st.text_input(
            "Headline par défaut", value=pi.get("headline_default", "")
        )
        n_summary = st.text_area(
            "Résumé par défaut", value=pi.get("summary_default", ""), height=100
        )

        st.markdown("**🌍 Langues** (une par ligne, format : `Langue | Niveau | Certification`)")
        langs = pi.get("languages", [])
        lang_text = "\n".join(
            f"{l.get('language','')} | {l.get('level','')} | {l.get('certification','')}"
            for l in langs
        )
        n_langs = st.text_area("Langues", value=lang_text, height=100, label_visibility="collapsed")

        if st.form_submit_button("💾 Enregistrer Identité", type="primary",
                                 use_container_width=True):
            pi["name"] = n_name.strip()
            pi["email"] = n_email.strip()
            pi["phone"] = n_phone.strip()
            pi["location"] = n_location.strip()
            pi["linkedin"] = n_linkedin.strip()
            pi["github"] = n_github.strip()
            pi["hobbies"] = [h.strip() for h in n_hobbies.split(",") if h.strip()]
            pi["headline_default"] = n_headline.strip()
            pi["summary_default"] = n_summary.strip()
            new_langs = []
            for line in n_langs.splitlines():
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                lang_obj = {"language": parts[0]}
                if len(parts) > 1 and parts[1]:
                    lang_obj["level"] = parts[1]
                if len(parts) > 2 and parts[2]:
                    lang_obj["certification"] = parts[2]
                new_langs.append(lang_obj)
            pi["languages"] = new_langs
            _save_profile(prof)
            st.success("✅ Identité enregistrée.")
            st.rerun()

# ─── FORMATION ──────────────────────────────────────────────────
with p_tab2:
    educations = prof.setdefault("education", [])
    st.caption(f"{len(educations)} formation(s) enregistrée(s).")

    for idx, edu in enumerate(educations):
        with st.expander(
            f"🎓 {edu.get('degree','(sans titre)')} — {edu.get('institution','?')}",
            expanded=False,
        ):
            with st.form(f"form_edu_{idx}"):
                e1, e2 = st.columns(2)
                with e1:
                    n_deg = st.text_input("Diplôme", value=edu.get("degree", ""), key=f"deg_{idx}")
                    n_inst = st.text_input("Établissement", value=edu.get("institution", ""), key=f"inst_{idx}")
                with e2:
                    n_per = st.text_input("Période", value=edu.get("period", ""), key=f"per_{idx}")
                    n_spec = st.text_input("Spécialisation", value=edu.get("specialization", ""), key=f"spec_{idx}")
                n_det = st.text_area("Détails", value=edu.get("details", ""), height=80, key=f"det_{idx}")

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.form_submit_button("💾 Mettre à jour", use_container_width=True):
                        edu["degree"] = n_deg.strip()
                        edu["institution"] = n_inst.strip()
                        edu["period"] = n_per.strip()
                        if n_spec.strip(): edu["specialization"] = n_spec.strip()
                        if n_det.strip(): edu["details"] = n_det.strip()
                        _save_profile(prof)
                        st.success("✅ Formation mise à jour.")
                        st.rerun()
                with bc2:
                    if st.form_submit_button("🗑️ Supprimer", use_container_width=True):
                        educations.pop(idx)
                        _save_profile(prof)
                        st.toast("Formation supprimée.")
                        st.rerun()

    with st.form("form_new_edu", clear_on_submit=True):
        st.markdown("**➕ Ajouter une formation**")
        c1, c2 = st.columns(2)
        with c1:
            new_deg = st.text_input("Diplôme")
            new_inst = st.text_input("Établissement")
        with c2:
            new_per = st.text_input("Période")
            new_spec = st.text_input("Spécialisation (optionnel)")
        new_det = st.text_area("Détails (optionnel)", height=70)
        if st.form_submit_button("➕ Ajouter", type="primary", use_container_width=True):
            if not new_deg.strip() or not new_inst.strip():
                st.warning("Le diplôme et l'établissement sont obligatoires.")
            else:
                educations.append({
                    "degree": new_deg.strip(),
                    "institution": new_inst.strip(),
                    "period": new_per.strip(),
                    **({"specialization": new_spec.strip()} if new_spec.strip() else {}),
                    **({"details": new_det.strip()} if new_det.strip() else {}),
                })
                _save_profile(prof)
                st.success("✅ Formation ajoutée.")
                st.rerun()

# ─── EXPÉRIENCES ────────────────────────────────────────────────
with p_tab3:
    exps = prof.setdefault("experience_stark", [])
    st.caption(
        f"{len(exps)} expérience(s) au format STARK (Situation, Tâche, Action, Résultat, Keywords). "
        "Format utilisé par Gemini pour générer un CV ciblé."
    )

    for idx, exp in enumerate(exps):
        with st.expander(
            f"💼 {exp.get('title','(sans titre)')} — {exp.get('company','?')}",
            expanded=False,
        ):
            with st.form(f"form_exp_{idx}"):
                x1, x2 = st.columns(2)
                with x1:
                    e_id = st.text_input("ID interne", value=exp.get("id", ""), key=f"eid_{idx}")
                    e_title = st.text_input("Intitulé", value=exp.get("title", ""), key=f"et_{idx}")
                    e_company = st.text_input("Entreprise", value=exp.get("company", ""), key=f"ec_{idx}")
                with x2:
                    e_period = st.text_input("Période", value=exp.get("period", ""), key=f"ep_{idx}")
                    e_tags = st.text_input(
                        "Tags profils (séparés par virgules)",
                        value=", ".join(exp.get("profiles_tags", [])),
                        key=f"etag_{idx}",
                    )
                    e_keywords = st.text_input(
                        "Keywords / outils (séparés par virgules)",
                        value=", ".join(exp.get("K", []) if isinstance(exp.get("K"), list) else []),
                        key=f"ek_{idx}",
                    )

                e_s = st.text_area("S — Situation", value=exp.get("S", ""), height=70, key=f"es_{idx}")
                e_t = st.text_area("T — Tâche", value=exp.get("T", ""), height=70, key=f"et2_{idx}")
                e_a = st.text_area("A — Action", value=exp.get("A", ""), height=100, key=f"ea_{idx}")
                e_r = st.text_area("R — Résultat", value=exp.get("R", ""), height=80, key=f"er_{idx}")

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.form_submit_button("💾 Mettre à jour", use_container_width=True):
                        exp["id"] = e_id.strip()
                        exp["title"] = e_title.strip()
                        exp["company"] = e_company.strip()
                        exp["period"] = e_period.strip()
                        exp["profiles_tags"] = [t.strip() for t in e_tags.split(",") if t.strip()]
                        exp["K"] = [k.strip() for k in e_keywords.split(",") if k.strip()]
                        exp["S"] = e_s.strip()
                        exp["T"] = e_t.strip()
                        exp["A"] = e_a.strip()
                        exp["R"] = e_r.strip()
                        _save_profile(prof)
                        st.success("✅ Expérience mise à jour.")
                        st.rerun()
                with bc2:
                    if st.form_submit_button("🗑️ Supprimer", use_container_width=True):
                        exps.pop(idx)
                        _save_profile(prof)
                        st.toast("Expérience supprimée.")
                        st.rerun()

    with st.form("form_new_exp", clear_on_submit=True):
        st.markdown("**➕ Ajouter une expérience**")
        n1, n2 = st.columns(2)
        with n1:
            ne_title = st.text_input("Intitulé")
            ne_company = st.text_input("Entreprise")
        with n2:
            ne_period = st.text_input("Période")
            ne_tags = st.text_input("Tags profils (séparés par virgules)", value="all")
        ne_a = st.text_area("Action principale (A)", height=80)
        ne_r = st.text_area("Résultat (R)", height=70)
        ne_k = st.text_input("Keywords (séparés par virgules)")
        if st.form_submit_button("➕ Ajouter", type="primary", use_container_width=True):
            if not ne_title.strip() or not ne_company.strip():
                st.warning("Intitulé et entreprise obligatoires.")
            else:
                new_id = f"EXP_{abs(hash(ne_title + ne_company)) % 10**6}"
                exps.append({
                    "id": new_id,
                    "title": ne_title.strip(),
                    "company": ne_company.strip(),
                    "period": ne_period.strip(),
                    "profiles_tags": [t.strip() for t in ne_tags.split(",") if t.strip()] or ["all"],
                    "S": "", "T": "",
                    "A": ne_a.strip(),
                    "R": ne_r.strip(),
                    "K": [k.strip() for k in ne_k.split(",") if k.strip()],
                })
                _save_profile(prof)
                st.success("✅ Expérience ajoutée.")
                st.rerun()

# ─── COMPÉTENCES ────────────────────────────────────────────────
with p_tab4:
    tax = prof.setdefault("skills_taxonomy", {})
    hard = tax.setdefault("hard_skills", [])
    soft = tax.setdefault("soft_skills", [])
    domain = tax.setdefault("domain_knowledge", [])

    with st.form("form_skills"):
        st.markdown("**🔧 Hard skills** (un par ligne, format : `Nom | Niveau`)")
        hs_text = "\n".join(
            f"{s.get('name','')} | {s.get('level','')}" if s.get("level") else s.get("name", "")
            for s in hard
        )
        n_hard = st.text_area("Hard skills", value=hs_text, height=180, label_visibility="collapsed")

        st.markdown("**🤝 Soft skills** (un par ligne)")
        n_soft = st.text_area(
            "Soft skills",
            value="\n".join(s if isinstance(s, str) else s.get("name", "") for s in soft),
            height=120, label_visibility="collapsed",
        )

        st.markdown("**🌐 Domaines d'expertise** (un par ligne)")
        n_dom = st.text_area(
            "Domaines",
            value="\n".join(domain),
            height=120, label_visibility="collapsed",
        )

        if st.form_submit_button("💾 Enregistrer Compétences", type="primary",
                                 use_container_width=True):
            new_hard = []
            for line in n_hard.splitlines():
                parts = [p.strip() for p in line.split("|")]
                if not parts or not parts[0]:
                    continue
                obj = {"name": parts[0]}
                if len(parts) > 1 and parts[1]:
                    obj["level"] = parts[1]
                new_hard.append(obj)
            tax["hard_skills"] = new_hard
            tax["soft_skills"] = [s.strip() for s in n_soft.splitlines() if s.strip()]
            tax["domain_knowledge"] = [d.strip() for d in n_dom.splitlines() if d.strip()]
            _save_profile(prof)
            st.success("✅ Compétences enregistrées.")
            st.rerun()

# ─── JSON BRUT ──────────────────────────────────────────────────
with p_tab5:
    st.caption(
        "Édition directe du JSON pour les champs avancés (profils, configs imbriquées). "
        "⚠️ Le JSON doit rester valide — un bouton de validation t'aide."
    )
    raw_json = st.text_area(
        "master_profile.json",
        value=json.dumps(prof, ensure_ascii=False, indent=2),
        height=500,
        key="raw_profile_json",
    )
    rj1, rj2 = st.columns(2)
    with rj1:
        if st.button("✅ Valider & Enregistrer", type="primary", use_container_width=True):
            try:
                parsed = json.loads(raw_json)
                _save_profile(parsed)
                st.success("✅ Profil enregistré avec succès.")
                st.rerun()
            except json.JSONDecodeError as exc:
                st.error(f"❌ JSON invalide : {exc}")
    with rj2:
        st.download_button(
            "⬇️ Télécharger le profil",
            data=json.dumps(prof, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="master_profile.json",
            mime="application/json",
            use_container_width=True,
        )

st.markdown("</div>", unsafe_allow_html=True)

st.caption("© Job Copilot · Studio de Candidature · Zein ELAJAMY — ENSEM 2026")
