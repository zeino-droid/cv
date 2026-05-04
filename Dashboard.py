"""
🎯 JOB COPILOT — Studio de Candidature (Single Page)
Zein ELAJAMY | Ingénieur R&D | ENSEM 2026
Refonte SPA : Smart Match → Studio (Modale) → Archives.
"""

import asyncio
import atexit
import base64
import json
import logging
import os
import sys
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from engine.database import STATUS_EMOJI, JobDatabase
from engine.history import ProfileHistory
from engine.ripple_engine import RippleEngine

_logger = logging.getLogger(__name__)

GOLDEN_THRESHOLD = 85

ASYNC_EXECUTOR = ThreadPoolExecutor(max_workers=1)
atexit.register(lambda: ASYNC_EXECUTOR.shutdown(wait=False, cancel_futures=True))


def run_coroutine_sync(coro, context: str = "operation"):
    """
    Exécute une coroutine de manière synchrone, en gérant les conflits de boucles d'événements.
    Essentiel pour faire tourner du code asynchrone (moteur CV) au sein de Streamlit (synchrone).
    
    Args:
        coro: La coroutine à exécuter.
        context (str): Nom de l'opération pour les logs d'erreurs.
    """
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

# ─── PERSONA SETUP ─────────────────────────────────────────────
if "selected_persona" not in st.session_state:
    st.session_state["selected_persona"] = "Industrial"

def get_persona_colors(persona: str):
    """Retourne la palette de couleurs selon la persona sélectionnée."""
    if persona == "Research":
        return {
            "brand": "#8b5cf6", # Deep Violet
            "brand-secondary": "#a78bfa",
            "glow": "rgba(139, 92, 246, 0.25)",
            "glow-subtle": "rgba(139, 92, 246, 0.1)",
            "gradient-text": "linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #8b5cf6 100%)",
            "bg-radial-1": "rgba(139, 92, 246, 0.08)",
            "bg-radial-2": "rgba(167, 139, 250, 0.05)"
        }
    elif persona == "Startup":
        return {
            "brand": "#f59e0b", # Amber/Orange
            "brand-secondary": "#fbbf24",
            "glow": "rgba(245, 158, 11, 0.25)",
            "glow-subtle": "rgba(245, 158, 11, 0.1)",
            "gradient-text": "linear-gradient(135deg, #ffffff 0%, #fbbf24 50%, #f59e0b 100%)",
            "bg-radial-1": "rgba(245, 158, 11, 0.08)",
            "bg-radial-2": "rgba(251, 191, 36, 0.05)"
        }
    else: # Industrial
        return {
            "brand": "#3b82f6", # Steel Blue
            "brand-secondary": "#60a5fa",
            "glow": "rgba(59, 130, 246, 0.25)",
            "glow-subtle": "rgba(59, 130, 246, 0.1)",
            "gradient-text": "linear-gradient(135deg, #ffffff 0%, #60a5fa 50%, #3b82f6 100%)",
            "bg-radial-1": "rgba(59, 130, 246, 0.08)",
            "bg-radial-2": "rgba(96, 165, 250, 0.05)"
        }

persona_colors = get_persona_colors(st.session_state["selected_persona"])

# ─── CSS PREMIUM (DARK / APPLE / NIKE) ───────────────────────────
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --brand: #8b5cf6;
            --brand-secondary: #3b82f6;
            --brand-glow: rgba(139, 92, 246, 0.25);
            --brand-glow-subtle: rgba(139, 92, 246, 0.1);
            --bg: #09090b;
            --card-bg: rgba(24, 24, 27, 0.4);
            --glass-bg: rgba(24, 24, 27, 0.2);
            --border: rgba(255, 255, 255, 0.08);
            --text-main: #ededed;
            --text-muted: #a1a1aa;
            --radius: 20px;
            --transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
        }
        
        .main { 
            font-family: 'Outfit', sans-serif; 
            background-color: var(--bg);
            background-image: 
                radial-gradient(at 0% 0%, rgba(139, 92, 246, 0.05) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(59, 130, 246, 0.05) 0px, transparent 50%);
        }
        
        [data-testid="stHeader"] { background: transparent; }

        /* Glassmorphism Core */
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }

        /* Pulse Animation for Shrink-Loop */
        @keyframes pulse-ring {
            0% { transform: scale(.33); }
            80%, 100% { opacity: 0; }
        }
        @keyframes pulse-dot {
            0% { transform: scale(.8); }
            50% { transform: scale(1); }
            100% { transform: scale(.8); }
        }
        .pulse-container {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: rgba(139, 92, 246, 0.1);
            border-radius: 12px;
            border: 1px solid rgba(139, 92, 246, 0.2);
            margin-bottom: 16px;
        }
        .pulse-dot {
            width: 12px;
            height: 12px;
            background-color: var(--brand);
            border-radius: 50%;
            position: relative;
            animation: pulse-dot 1.5s cubic-bezier(0.455, 0.03, 0.515, 0.955) infinite;
        }
        .pulse-dot::before {
            content: '';
            position: absolute;
            width: 300%;
            height: 300%;
            top: -100%;
            left: -100%;
            border-radius: 45px;
            background-color: var(--brand);
            animation: pulse-ring 1.5s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
        }

        [data-testid="stMarkdownContainer"] code {
            color: var(--brand) !important;
            background-color: rgba(255, 255, 255, 0.05) !important;
            padding: 2px 6px !important;
            border-radius: 4px !important;
        }

        mark {
            background-color: rgba(139, 92, 246, 0.3) !important;
            color: var(--text-main) !important;
            border-radius: 4px;
            padding: 0 4px;
        }

        [data-testid="stExpander"] summary p {
            color: var(--text-main) !important;
            font-weight: 600 !important;
        }

        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { width: 0 !important; }
        
        h1, h2, h3, h4 {
            font-family: 'Outfit', sans-serif !important;
            font-weight: 800 !important;
            letter-spacing: -0.02em !important;
        }

        .hero-h1 {
            font-size: 64px !important;
            background: linear-gradient(135deg, #ffffff 0%, #a78bfa 50%, #60a5fa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px; line-height: 1.1;
            font-family: 'Outfit', sans-serif !important; font-weight: 800;
            animation: fadeInUp 0.8s ease-out;
        }
        
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }

        .section-card {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 32px;
            margin-bottom: 24px;
            transition: var(--transition);
        }
        .section-card:hover {
            border-color: rgba(139, 92, 246, 0.3);
            box-shadow: 0 12px 40px rgba(0,0,0,0.4);
        }

        /* Compare View Highlights */
        .diff-added {
            background-color: rgba(139, 92, 246, 0.2);
            color: #d8b4fe !important;
            border-bottom: 2px solid var(--brand);
            padding: 0 2px;
        }

        /* Bulk Actions Bar */
        .bulk-actions-bar {
            background: rgba(139, 92, 246, 0.08);
            backdrop-filter: blur(10px);
            border: 1px dashed var(--brand);
            border-radius: 16px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 4px 20px rgba(139, 92, 246, 0.1);
        }

        /* KPI metric cards */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 20px;
            transition: var(--transition);
        }
        [data-testid="stMetric"]:hover {
            border-color: var(--brand);
            transform: translateY(-4px);
            background: rgba(255, 255, 255, 0.05);
        }

        div.stButton > button {
            background: linear-gradient(135deg, var(--brand) 0%, var(--brand-secondary) 100%) !important;
            color: white !important;
            border-radius: 14px !important;
            font-weight: 700 !important;
            padding: 12px 24px !important;
            border: none !important;
            transition: var(--transition) !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            box-shadow: 0 4px 15px var(--brand-glow);
        }
        div.stButton > button:hover {
            transform: scale(1.03);
            box-shadow: 0 8px 25px var(--brand-glow);
        }

        /* Custom Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: rgba(255,255,255,0.03);
            border-radius: 12px 12px 0 0;
            padding: 10px 20px;
            border: 1px solid var(--border);
            border-bottom: none;
        }
        .stTabs [data-baseweb="tab--active"] {
            background-color: var(--brand-glow-subtle);
            border-top: 2px solid var(--brand);
        }

        /* Application Pipeline */
        .pipeline-container {
            display: flex;
            align-items: center;
            gap: 6px;
            margin: 10px 0;
            font-family: 'Outfit', sans-serif;
        }
        .pipeline-step {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-muted);
            transition: var(--transition);
            white-space: nowrap;
        }
        .pipeline-step.active {
            background: var(--brand-glow-subtle);
            border-color: var(--brand);
            color: var(--text-main);
            box-shadow: 0 0 15px var(--brand-glow-subtle);
        }
        .pipeline-arrow {
            color: var(--text-muted);
            opacity: 0.4;
            font-size: 0.8rem;
        }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg); }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--brand); }

        /* Ghost Preview Box */
        .ghost-preview {
            background: rgba(139, 92, 246, 0.05);
            border: 1px dashed rgba(139, 92, 246, 0.3);
            border-radius: 12px;
            padding: 16px;
            margin-top: 10px;
            animation: fadeIn 0.5s ease-out;
        }
        .ghost-label {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--brand);
            font-weight: 800;
            margin-bottom: 4px;
        }
        .ghost-text {
            font-size: 0.9rem;
            color: var(--text-muted);
            font-style: italic;
            line-height: 1.4;
        }
        
        /* Ripple Search Styles */
        .ripple-card {
            background: rgba(59, 130, 246, 0.05);
            border: 1px solid rgba(59, 130, 246, 0.2);
            border-radius: 16px;
            padding: 16px;
            margin-top: 12px;
            animation: slideIn 0.4s ease-out;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .ripple-title {
            font-size: 0.8rem;
            font-weight: 800;
            color: #60a5fa;
            text-transform: uppercase;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .competitor-link {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--border);
            border-radius: 8px;
            font-size: 0.85rem;
            color: var(--text-main);
            text-decoration: none;
            margin-right: 8px;
            margin-bottom: 8px;
            transition: var(--transition);
        }
        .competitor-link:hover {
            border-color: #60a5fa;
            background: rgba(59, 130, 246, 0.1);
            transform: translateY(-2px);
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
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


def render_quality_badge(model_name: str, latency: float = None) -> str:
    """Affiche un badge stylisé pour le modèle LLM utilisé et sa latence."""
    if not model_name:
        return ""
    
    # Choix de l'icône selon le modèle
    emoji = "💎" if "Gemini" in model_name else ("🦙" if "Ollama" in model_name else "🤖")
    
    # Détection si local
    is_local = "Ollama" in model_name or "MLX" in model_name
    
    badge_html = f"""
    <div style='display:inline-flex; align-items:center; gap:8px; background:var(--glass-bg); 
                border:1px solid var(--border); border-radius:12px; padding:4px 10px; margin-bottom:12px;'>
        <span style='font-size:0.8rem; font-weight:600; color:var(--brand);'>{emoji} {model_name}</span>
    """
    
    if latency and is_local:
        badge_html += f"""
        <span style='width:1px; height:12px; background:var(--border);'></span>
        <span style='font-size:0.75rem; color:var(--text-muted);'>⏱️ {latency:.1f}s</span>
        """
    
    badge_html += "</div>"
    return badge_html


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


def render_pdf_viewer(pdf_path: str, height: int = 1000):
    """
    Rendu d'un PDF via un <iframe> en base64.
    Offre une expérience plus fluide que le rendu d'images (zoom, sélection, etc.).
    """
    try:
        with open(pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # On utilise un conteneur HTML avec un peu de style pour l'intégration premium
        pdf_display = f'''
            <div style="border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: white;">
                <iframe src="data:application/pdf;base64,{base64_pdf}#view=FitH" 
                        width="100%" height="{height}" 
                        type="application/pdf"
                        style="border:none;">
                </iframe>
            </div>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erreur d'affichage PDF : {e}")


def render_ghost_badges(job: dict) -> str:
    """Génère les badges pour les benefits détectés (Remote, Salary, etc.)."""
    badges = []
    
    # Check for remote work
    if job.get("remote"):
        badges.append("🌍 Remote")
    
    # Check for salary information
    if job.get("salary_min") or job.get("salary_max"):
        min_sal = job.get("salary_min", "?")
        max_sal = job.get("salary_max", "?")
        if min_sal != "?" and max_sal != "?":
            badges.append(f"💰 {min_sal}-{max_sal}k")
        else:
            badges.append("💰 Salary")
    
    # Check for immediate availability
    if job.get("immediate"):
        badges.append("⚡ Immédiat")
    
    if not badges:
        return ""
    
    badge_html = " ".join([f'<span class="ghost-badge">{badge}</span>' for badge in badges])
    return f'<div class="ghost-badges-container">{badge_html}</div>'


def render_status_pipeline(job: dict) -> str:
    """Génère le HTML pour la barre de progression visuelle de la candidature."""
    has_cv = bool(job.get("cv_path"))
    has_letter = bool(job.get("letter_path"))
    status = job.get("status", "new")
    is_applied = status in ("sent", "applied", "interview", "offer", "rejected")
    
    steps = [
        {"label": "🔍 Matched", "active": True},
        {"label": "📄 CV Ready", "active": has_cv},
        {"label": "✉️ Letter Ready", "active": has_letter},
        {"label": "🚀 Applied", "active": is_applied},
    ]
    
    html = '<div class="pipeline-container">'
    for i, step in enumerate(steps):
        active_class = "active" if step["active"] else ""
        html += f'<div class="pipeline-step {active_class}">{step["label"]}</div>'
        if i < len(steps) - 1:
            html += '<div class="pipeline-arrow">→</div>'
    html += '</div>'
    return html


def render_ripple_results(competitors: list[dict]) -> str:
    """Génère le HTML pour les résultats de la recherche Ripple."""
    if not competitors:
        return ""
    
    links_html = ""
    for comp in competitors:
        name = comp.get("name", "Entreprise")
        url = comp.get("url", "#")
        sector = comp.get("sector", "")
        links_html += f"""
        <a href="{url}" target="_blank" class="competitor-link" title="{sector}">
            🏢 {name}
        </a>
        """
    
    html = f"""
    <div class="ripple-card">
        <div class="ripple-title">🗺️ Ripple Search : Concurrents R&D</div>
        <div style="display: flex; flex-wrap: wrap;">
            {links_html}
        </div>
        <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 4px; opacity: 0.7;">
            * Liens générés par IA vers les pages carrières probables.
        </div>
    </div>
    """
    return html


# ─── GÉNÉRATION (CV + LETTRE) ────────────────────────────────────
def generate_documents(job: dict, gen_cv: bool, gen_letter: bool, use_llm: bool,
                       headline_override: str | None = None,
                       summary_override: str | None = None,
                       section_overrides: dict | None = None,
                       photo_path: str | None = None,
                       persona: str = "Industrial",
                       progress_callback: callable | None = None) -> dict:
    """Lance la génération CV + lettre via les modules existants.

    `section_overrides` permet de réinjecter des éditions ciblées par section
    (puces d'expérience, compétences, projets…) — voir
    `engine.cv_generator.PersonalCVGenerator._apply_text_overrides` pour le schéma.

    `photo_path` est le chemin absolu de la photo de profil uploadée (st.session_state.photo_path).
    Si None ou absent, aucune photo n'est ajoutée au CV.
    """
    profile = load_profile()
    if not profile:
        raise FileNotFoundError(
            "Le profil maître est vide ou introuvable "
            "(profiles/master_profile.json). Remplis la section ④ Profil d'abord."
        )
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
                section_overrides=section_overrides or None,
                photo_path=photo_path or None,
                persona=persona,
                progress_callback=progress_callback,
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
                from engine.cv_generator import PersonalCVGenerator as _CG
                from Pipeline import generate_cover_letter_llm
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

        # Tenter le rendu PDF via Typst, fallback texte
        from engine.letter_renderer import LetterRenderer, build_letter_data
        renderer = LetterRenderer()
        pdf_out = out_dir / "lettre.pdf"
        try:
            # Extraire les paragraphes du corps de la lettre
            import re as _re
            raw_paragraphs = [
                p.strip() for p in _re.split(r"\n\s*\n", letter_text)
                if p.strip()
                and not p.strip().startswith("Objet")
                and not p.strip().startswith("Madame")
                and "salutations" not in p.lower()
                and "@" not in p
                and not _re.match(r"^\+?\d", p.strip())
                and not _re.match(r"^\d{2}/\d{2}/\d{4}$", p.strip())
            ]
            paragraphs = raw_paragraphs if raw_paragraphs else [letter_text]
            letter_data = build_letter_data(profile, job, paragraphs)
            pdf_result = renderer.render(letter_data, pdf_out)
            if pdf_result and pdf_result.exists():
                letter_path = str(pdf_result)
            else:
                letter_path = str(out_dir / "lettre.txt")
                Path(letter_path).write_text(letter_text, encoding="utf-8")
        except Exception:
            letter_path = str(out_dir / "lettre.txt")
            Path(letter_path).write_text(letter_text, encoding="utf-8")
        # Toujours sauvegarder le fallback texte en parallèle
        txt_fallback = out_dir / "lettre.txt"
        if not txt_fallback.exists():
            txt_fallback.write_text(letter_text, encoding="utf-8")

    if cv_path or letter_path:
        model_name = cv_result.get("llm_name") if gen_cv else None
        latency = cv_result.get("llm_latency") if gen_cv else None
        db.save_generation(job["id"], cv_path, letter_path, model=model_name, latency=latency)

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
        "llm_name": cv_result.get("llm_name") if gen_cv else None,
    }


# ─── COUCHE SERVICE : logique métier extraite de studio_dialog ───
# Les implémentations vivent dans engine/studio_service.py (testable sans Streamlit).
# Ces fonctions sont de fines enveloppes qui injectent les dépendances globales.
from engine.studio_service import (
    _init_gen_state,
)
from engine.studio_service import (
    mark_application_as_sent as _svc_mark_sent,
)
from engine.studio_service import (
    save_final_candidate_version as _svc_save_final,
)


def save_final_candidate_version(
    job_id: str,
    job: dict,
    gen_state: dict,
    photo_path: str | None = None,
    persona: str = "Industrial",
) -> dict:
    """Recompile le CV, persiste la lettre et archive les versions finales.

    Délègue à :func:`engine.studio_service.save_final_candidate_version` en
    injectant les dépendances du module (``db``, ``ROOT``, …).
    """
    return _svc_save_final(
        job_id, job, gen_state, photo_path, persona,
        db=db,
        root=ROOT,
        generate_documents_fn=generate_documents,
        safe_filename_fn=safe_filename,
    )


def mark_application_as_sent(job_id: str, gen_state: dict) -> None:
    """Marque la candidature comme envoyée. Délègue à engine.studio_service."""
    _svc_mark_sent(job_id, gen_state, db=db)


# ─── COPILOTE IA : réécriture ciblée via le LLM existant ─────────
def _rewrite_section_call(
    section_key: str,
    instruction: str,
    profile: dict,
    cv_data: dict,
    job: dict,
    item_id: str | None = None,
) -> tuple[object, str | None]:
    """Appelle le rewriter section-par-section (cf. engine.section_rewrite).

    Renvoie `(valeur_typée, message_erreur)`. La valeur est typée selon la section
    (str pour headline/summary/letter/description, list[str] pour les puces
    d'expérience et les listes de compétences, str pour les mots-clés projet).
    """
    from engine.cv_generator import PersonalCVGenerator
    from engine.section_rewrite import rewrite_section

    try:
        gen = PersonalCVGenerator()
    except Exception as exc:
        return None, f"Impossible d'initialiser le moteur : {exc}"

    llm = getattr(gen, "llm", None)
    if llm is None:
        return None, (
            "Aucun moteur LLM disponible. Vérifie que GEMINI_API_KEY est bien "
            "configurée dans les secrets Replit."
        )

    async def _go():
        return await rewrite_section(
            llm,
            section_key=section_key,
            profile=profile,
            cv_data=cv_data,
            job=job,
            instruction=instruction,
            item_id=item_id,
        )

    try:
        return run_coroutine_sync(_go(), context=f"section_rewrite:{section_key}")
    except Exception as exc:
        return None, f"Erreur d'exécution asynchrone : {exc}"


def _rewrite_letter_call(
    instruction: str,
    current_letter: str,
    job: dict,
) -> tuple[str | None, str | None]:
    """Réécrit la lettre de motivation entière en s'appuyant sur la version actuelle."""
    from engine.cv_generator import PersonalCVGenerator

    try:
        gen = PersonalCVGenerator()
    except Exception as exc:
        return None, f"Impossible d'initialiser le moteur : {exc}"

    llm = getattr(gen, "llm", None)
    if llm is None:
        return None, "Aucun moteur LLM disponible. Vérifie GEMINI_API_KEY."

    prompt = f"""Tu es un expert en rédaction de lettres de motivation pour ingénieurs en France.

LETTRE ACTUELLE :
{current_letter or '(vide)'}

POSTE VISÉ : {job.get('title','')} chez {job.get('company','')} — {job.get('location','')}
COMPÉTENCES CIBLÉES : {', '.join((job.get('matched_skills') or [])[:8])}
EXTRAIT DE L'OFFRE :
{(job.get('description') or '')[:1200]}

INSTRUCTION DE L'UTILISATEUR : {instruction}

RÈGLES :
- Garde une structure 3-4 paragraphes (intro / valeur / motivation / call-to-action).
- Ton pro mais incarné (1ère personne).
- 250-400 mots.
- N'ajoute AUCUN préambule type "Voici la lettre :".
- Réponds UNIQUEMENT avec la lettre réécrite.
"""

    async def _go():
        try:
            return await llm.generate(prompt, temperature=0.4)
        except Exception as exc:
            return f"__ERR__{exc}"

    try:
        result = run_coroutine_sync(_go(), context="letter_rewrite")
    except Exception as exc:
        return None, f"Erreur d'exécution asynchrone : {exc}"

    if result is None:
        return None, getattr(llm, "last_error_message", None) or "Aucune réponse du LLM."
    if isinstance(result, str) and result.startswith("__ERR__"):
        return None, f"Erreur LLM : {result[7:]}"
    if isinstance(result, str) and result.strip():
        return result.strip(), None
    return None, "Le LLM n'a rien renvoyé."


# ─── ÉDITEUR DE SECTION (nouvelle UI Studio) ────────────────────
def _section_block(
    *,
    section_key: str,
    job_id: str,
    job: dict,
    profile: dict,
    cv_data: dict,
    gen_state: dict,
    state_key: str,
    item_id: str | None = None,
    item_label: str | None = None,
):
    """Affiche un bloc d'édition pour UNE section ciblée.

    Le bloc montre :
      - la valeur actuelle (lecture seule)
      - un champ d'instruction
      - un bouton "Améliorer avec l'IA"
      - quand une proposition existe : preview + Appliquer / Annuler
    Les overrides validés sont stockés dans `gen_state["section_overrides"]`.
    """
    from engine.section_rewrite import EDITABLE_SECTIONS, extract_current

    spec = EDITABLE_SECTIONS.get(section_key, {})
    icon = spec.get("icon", "")
    label = spec.get("label", section_key)
    value_type = spec.get("value_type", "str")

    # Clé unique pour widgets (intègre item_id si applicable)
    suffix = f"{section_key}_{item_id}" if item_id else section_key
    suffix = suffix.replace(" ", "_").replace("/", "_")

    # Valeur actuelle = override si existe, sinon valeur du CV courant
    overrides = gen_state.setdefault("section_overrides", {})
    if spec.get("per_item"):
        bucket = overrides.get(section_key, {})
        current_override = bucket.get(item_id)
    else:
        current_override = overrides.get(section_key)

    if current_override is not None:
        current_val = current_override
    else:
        current_val = extract_current(cv_data, section_key, item_id=item_id)

    # ── Affichage de la valeur actuelle ──
    title = f"**{icon} {label}**"
    if item_label:
        title += f" — *{item_label}*"
    st.markdown(title)

    if current_override is not None:
        st.caption("✏️ Édition appliquée (sera utilisée à la recompilation)")

    if value_type == "list_str":
        current_str = "\n".join(f"• {x}" for x in (current_val or []))
        st.text_area(
            "Contenu actuel",
            value=current_str,
            height=80 if section_key == "achievements" else 110,
            disabled=True,
            key=f"sec_show_{suffix}_{job_id}",
            label_visibility="collapsed",
        )
    else:
        height = {
            "headline": 60,
            "summary": 110,
            "project_description": 60,
            "project_keywords": 60,
            "letter": 240,
        }.get(section_key, 80)
        st.text_area(
            "Contenu actuel",
            value=str(current_val or ""),
            height=height,
            disabled=True,
            key=f"sec_show_{suffix}_{job_id}",
            label_visibility="collapsed",
        )

    # ── Champ instruction + bouton IA ──
    instruction = st.text_input(
        "Demande à l'IA",
        placeholder="Ex : Ajoute une mention CFD · Rends plus concret · Insiste sur Python",
        key=f"sec_instr_{suffix}_{job_id}",
    )

    c_ai, c_clear = st.columns([3, 1])
    with c_ai:
        run_ai = st.button(
            f"🤖 Améliorer avec l'IA",
            key=f"sec_ai_{suffix}_{job_id}",
            use_container_width=True,
            type="primary",
        )
    with c_clear:
        clear_btn = st.button(
            "↩️ Reset" if current_override is not None else "—",
            key=f"sec_clear_{suffix}_{job_id}",
            use_container_width=True,
            disabled=current_override is None,
            help="Annule l'édition et revient à la version générée",
        )

    if clear_btn and current_override is not None:
        if spec.get("per_item"):
            overrides[section_key] = {
                k: v for k, v in overrides.get(section_key, {}).items() if k != item_id
            }
            if not overrides[section_key]:
                del overrides[section_key]
        else:
            overrides.pop(section_key, None)
        st.session_state[state_key] = gen_state
        st.rerun()

    if run_ai:
        if not instruction.strip():
            st.warning("Précise ton instruction avant de lancer l'IA.")
        else:
            with st.spinner("L'IA retravaille cette section..."):
                if section_key == "letter":
                    val, err = _rewrite_letter_call(
                        instruction=instruction.strip(),
                        current_letter=str(current_val or ""),
                        job=job,
                    )
                else:
                    val, err = _rewrite_section_call(
                        section_key=section_key,
                        instruction=instruction.strip(),
                        profile=profile,
                        cv_data=cv_data,
                        job=job,
                        item_id=item_id,
                    )
            if err or val is None:
                st.error(f"❌ {err or 'Réponse vide.'}")
            else:
                # Stocker comme proposition en attente (pas appliqué tant que pas validé)
                proposals = gen_state.setdefault("section_proposal", {})
                prop_key = f"{section_key}::{item_id}" if item_id else section_key
                proposals[prop_key] = val
                st.session_state[state_key] = gen_state
                st.rerun()

    # ── Affichage proposition en attente ──
    proposals = gen_state.get("section_proposal", {})
    prop_key = f"{section_key}::{item_id}" if item_id else section_key
    proposal = proposals.get(prop_key)
    if proposal is not None:
        st.markdown("##### 💡 Proposition de l'IA")
        if value_type == "list_str":
            prop_str = "\n".join(f"• {x}" for x in proposal)
        else:
            prop_str = str(proposal)
        st.text_area(
            "Proposition",
            value=prop_str,
            height=120,
            key=f"sec_prop_{suffix}_{job_id}",
            label_visibility="collapsed",
        )
        cap, can = st.columns(2)
        with cap:
            if st.button("✅ Appliquer", type="primary",
                         key=f"sec_apply_{suffix}_{job_id}",
                         use_container_width=True):
                if section_key == "letter":
                    gen_state["letter_text"] = str(proposal)
                else:
                    if spec.get("per_item"):
                        bucket = overrides.setdefault(section_key, {})
                        bucket[item_id] = proposal
                    else:
                        overrides[section_key] = proposal
                proposals.pop(prop_key, None)
                
                # [UX OPTIMIZATION] Auto-recompile the PDF immediately
                with st.spinner("Recompilation automatique..."):
                    try:
                        result = generate_documents(
                            job, gen_cv=True, gen_letter=False, use_llm=False,
                            section_overrides=gen_state.get("section_overrides") or {},
                            photo_path=st.session_state.get("photo_path"),
                            persona=st.session_state.get("selected_persona", "Industrial"),
                        )
                        gen_state["cv_path"] = result.get("cv_path", "")
                        cv_res = result.get("cv_result") or {}
                        if cv_res.get("cv_data"):
                            gen_state["cv_data"] = cv_res["cv_data"]
                    except Exception as exc:
                        st.error(f"Erreur de recompilation : {exc}")

                st.session_state[state_key] = gen_state
                st.rerun()
        with can:
            if st.button("❌ Annuler",
                         key=f"sec_cancel_{suffix}_{job_id}",
                         use_container_width=True):
                proposals.pop(prop_key, None)
                st.session_state[state_key] = gen_state
                st.rerun()


def _render_section_editor(job: dict, profile: dict, gen_state: dict,
                            state_key: str, job_id: str):
    """Onglets section-par-section pour éditer le CV + lettre avec aide de l'IA."""
    from engine.section_rewrite import list_experience_items, list_project_items

    cv_data_src = gen_state.get("cv_data") or {}
    if not cv_data_src:
        st.info(
            "Le CV n'a pas encore été généré pour cette offre. "
            "Lance d'abord la génération initiale."
        )
        return

    # Enrichit cv_data avec letter_text courant pour que extract_current(letter) fonctionne
    cv_data = dict(cv_data_src)
    cv_data["letter_text"] = gen_state.get("letter_text", "") or ""

    st.markdown("##### ✨ Édition assistée par l'IA")
    st.caption(
        "Choisis une section, formule ta demande, valide la proposition. "
        "L'IA voit ton profil maître + l'offre pour adapter au plus juste."
    )

    # Avertit si des overrides ne matchent plus aucun item du CV courant
    from engine.section_rewrite import find_unapplied_overrides
    unmatched = find_unapplied_overrides(cv_data, gen_state.get("section_overrides") or {})
    if unmatched:
        with st.expander(f"⚠️ {len(unmatched)} édition(s) en attente sans correspondance dans le CV courant",
                         expanded=False):
            for msg in unmatched:
                st.warning(msg)
            st.caption(
                "Ces éditions concernent des items qui ne sont plus présents dans le CV "
                "(par ex. une expérience écartée par la sélection automatique). "
                "Elles seront ignorées tant qu'elles ne matchent pas un id présent."
            )

    exp_items = list_experience_items(cv_data)
    proj_items = list_project_items(cv_data)

    tab_labels = [
        "🎯 Accroche",
        "📝 Résumé",
        "💼 Expériences",
        "🚀 Projets",
        "🛠️ Compétences",
        "✉️ Lettre",
    ]
    tabs = st.tabs(tab_labels)

    common = dict(
        job=job, profile=profile, cv_data=cv_data,
        gen_state=gen_state, state_key=state_key, job_id=job_id,
    )

    # 🎯 Accroche
    with tabs[0]:
        _section_block(section_key="headline", **common)

    # 📝 Résumé
    with tabs[1]:
        _section_block(section_key="summary", **common)

    # 💼 Expériences (sélecteur d'expérience)
    with tabs[2]:
        if not exp_items:
            st.info("Aucune expérience dans le CV courant.")
        else:
            labels = [e["label"] for e in exp_items]
            chosen = st.selectbox(
                "Quelle expérience retravailler ?",
                options=range(len(labels)),
                format_func=lambda i: labels[i],
                key=f"sel_exp_{job_id}",
            )
            chosen_exp = exp_items[chosen]
            _section_block(
                section_key="achievements",
                item_id=chosen_exp["id"],
                item_label=chosen_exp["label"],
                **common,
            )

    # 🚀 Projets (sélecteur + 2 sous-éditions : description + mots-clés)
    with tabs[3]:
        if not proj_items:
            st.info("Aucun projet dans le CV courant.")
        else:
            labels = [p["label"] for p in proj_items]
            chosen = st.selectbox(
                "Quel projet retravailler ?",
                options=range(len(labels)),
                format_func=lambda i: labels[i],
                key=f"sel_proj_{job_id}",
            )
            chosen_proj = proj_items[chosen]
            _section_block(
                section_key="project_description",
                item_id=chosen_proj["id"],
                item_label=chosen_proj["label"],
                **common,
            )
            st.markdown("---")
            _section_block(
                section_key="project_keywords",
                item_id=chosen_proj["id"],
                item_label=chosen_proj["label"],
                **common,
            )

    # 🛠️ Compétences (3 sous-onglets)
    with tabs[4]:
        sub_tabs = st.tabs(["🛠️ Techniques", "🧠 Métier", "🤝 Savoir-être"])
        with sub_tabs[0]:
            _section_block(section_key="skills_hard", **common)
        with sub_tabs[1]:
            _section_block(section_key="skills_domain", **common)
        with sub_tabs[2]:
            _section_block(section_key="skills_soft", **common)

    # ✉️ Lettre
    with tabs[5]:
        # Pour la lettre, on autorise aussi une édition manuelle directe
        st.markdown("**✉️ Lettre de motivation**")
        edited_letter = st.text_area(
            "Modifie directement la lettre ici, ou utilise l'IA en dessous",
            value=gen_state.get("letter_text", ""),
            height=240,
            key=f"letter_manual_{job_id}",
        )
        if edited_letter != gen_state.get("letter_text", ""):
            gen_state["letter_text"] = edited_letter
            st.session_state[state_key] = gen_state
        st.markdown("---")
        _section_block(section_key="letter", **common)


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
        f"<span style='font-size:0.85rem;color:var(--text-muted);font-weight:500;'>"
        f"— {job.get('company','?')} · 📍 {job.get('location','?')}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='margin:6px 0 12px 0; display:flex; align-items:center; gap:12px;'>"
        f"<span class='score-pill {score_class(score)}'>{score}% Fit</span> "
        f"<span class='score-pill' style='background:var(--brand-glow-subtle);"
        f"color:var(--brand);border:1px solid var(--brand-glow);'>"
        f"{STATUS_EMOJI.get(job.get('status','new'),'•')} {job.get('status','new')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(render_status_pipeline(job), unsafe_allow_html=True)

    # Initialise les clés gen_state obligatoires (lettre heuristique + overrides)
    _init_gen_state(gen_state, profile, job)
    st.session_state[state_key] = gen_state

    # ── 4 ONGLETS ───────────────────────────────────────────────
    tab_analyse, tab_studio, tab_compare, tab_skills = st.tabs(
        ["🔬 Analyse", "🎬 Studio CV + Lettre", "🌗 Compare View", "☁️ Skill Cloud"]
    )

    # === ONGLET 1 : ANALYSE =====================================
    with tab_analyse:
        from engine.studio_analysis import (
            build_skill_matrix,
            render_heatmap_html,
            render_radar_chart,
        )
        matrix = build_skill_matrix(profile, job)
        
        # Skill Heatmap & Radar Chart Side by Side
        acol1, acol2 = st.columns([3, 2])
        with acol1:
            st.components.v1.html(render_heatmap_html(matrix), height=520, scrolling=True)
        with acol2:
            st.markdown("<div style='text-align:center;color:var(--brand);font-weight:700;font-size:0.85rem;margin-bottom:10px;'>📊 AUTHORITY COVERAGE</div>", unsafe_allow_html=True)
            st.components.v1.html(render_radar_chart(matrix), height=320)
            
            # Authority / Skill Floor Check
            unproven = [s for s in matrix["matched"] if s not in matrix.get("proofs", {})]
            if unproven:
                st.warning(f"⚠️ **Skill Floor Warning** : {len(unproven)} compétences matchées n'ont pas de preuve explicite dans tes expériences ({', '.join(unproven[:3])}).")
            else:
                st.success("✅ **Authority Engine** : 100% des compétences matchées sont prouvées par tes expériences.")

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
                "<div style='background:var(--brand-glow-subtle);border:1px solid "
                "var(--brand-glow);border-radius:8px;padding:14px;"
                "color:var(--text-main);font-size:0.92rem;line-height:1.55;'>"
                "<strong>🧠 Génération intelligente.</strong> "
                "Gemini va lire ton profil complet et l'offre ciblée, puis "
                "rédiger un CV professionnel et une lettre personnalisée. "
                "Tu pourras ensuite tout éditer ou demander des retouches au copilote."
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("&nbsp;")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🚀 Générer CV + Lettre (Single)",
                             type="primary", use_container_width=True,
                             key=f"btn_studio_gen_{job_id}"):
                    
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    
                    def update_progress(msg, progress):
                        with status_placeholder.container():
                            st.markdown(
                                f"""
                                <div class="pulse-container">
                                    <div class="pulse-dot"></div>
                                    <div style="color:var(--brand); font-weight:700; font-size:0.9rem;">{msg}</div>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )
                        progress_bar.progress(progress)

                    try:
                        result = generate_documents(
                            job, gen_cv=True, gen_letter=True, use_llm=True,
                            section_overrides=gen_state.get("section_overrides") or {},
                            photo_path=st.session_state.get("photo_path"),
                            persona=st.session_state.get("selected_persona", "Industrial"),
                            progress_callback=update_progress,
                        )
                        gen_state.update(result)
                        if result.get("letter_text"):
                            gen_state["letter_text"] = result["letter_text"]
                        cv_res = result.get("cv_result") or {}
                        if cv_res.get("cv_data"):
                            gen_state["cv_data"] = cv_res["cv_data"]
                        gen_state["studio_initialized"] = True
                        st.session_state[state_key] = gen_state
                        
                        update_progress("✅ Génération terminée !", 1.0)
                        _time.sleep(0.5)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Erreur Gemini : {exc}")
            
            with c2:
                if st.button("🌓 Generate Both (Persona Duel)",
                             use_container_width=True,
                             key=f"btn_studio_duel_{job_id}",
                             help="Génère deux versions : Industrielle et Recherche. Tu choisiras la meilleure ensuite."):
                    
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    
                    def update_progress(msg, progress):
                        with status_placeholder.container():
                            st.markdown(
                                f"<div class='pulse-container'><div class='pulse-dot'></div>"
                                f"<div style='color:var(--brand); font-weight:700; font-size:0.9rem;'>{msg}</div></div>", 
                                unsafe_allow_html=True
                            )
                        progress_bar.progress(progress)

                    try:
                        # 1. Industrial Version
                        update_progress("⚙️ Génération version Industrielle...", 0.1)
                        res_ind = generate_documents(
                            job, gen_cv=True, gen_letter=True, use_llm=True,
                            persona="Industrial", progress_callback=lambda m, p: update_progress(f"⚙️ Ind: {m}", 0.1 + p*0.4)
                        )
                        
                        # 2. Research Version
                        update_progress("🔬 Génération version Recherche...", 0.5)
                        res_res = generate_documents(
                            job, gen_cv=True, gen_letter=False, use_llm=True, # Letter only once or for Ind
                            persona="Research", progress_callback=lambda m, p: update_progress(f"🔬 Res: {m}", 0.5 + p*0.4)
                        )
                        
                        gen_state["duel_industrial"] = res_ind
                        gen_state["duel_research"] = res_res
                        gen_state["is_duel_mode"] = True
                        gen_state["studio_initialized"] = True
                        
                        # Set a default so Studio doesn't crash if they switch tabs before picking
                        gen_state.update(res_ind)
                        
                        st.session_state[state_key] = gen_state
                        update_progress("✅ Duel prêt !", 1.0)
                        _time.sleep(0.5)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"❌ Erreur Duel : {exc}")

        # ─── PHASE 2 : aperçu PDF + édition + copilote ─────────
        else:
            # 🤖 Quality Badge
            badge_html = render_quality_badge(
                gen_state.get("llm_name") or job.get("generation_model"),
                gen_state.get("llm_latency") or job.get("generation_latency")
            )
            if badge_html:
                st.markdown(badge_html, unsafe_allow_html=True)

            preview_col, edit_col = st.columns([1, 1], gap="medium")

            # ───── COLONNE GAUCHE : APERÇU PDF ─────────────────
            with preview_col:
                st.markdown("##### 📄 Aperçu PDF live")
                cv_preview = gen_state.get("cv_path") or ""
                if cv_preview and Path(cv_preview).exists() and cv_preview.endswith(".pdf"):
                    # Nouvelle méthode : Iframe PDF pour une interaction complète
                    render_pdf_viewer(cv_preview, height=950)
                    
                    # Fallback discret si l'utilisateur préfère le téléchargement
                    with open(cv_preview, "rb") as f:
                        st.download_button(
                            "💾 Télécharger cette version",
                            data=f.read(),
                            file_name=Path(cv_preview).name,
                            mime="application/pdf",
                            key=f"dl_preview_{job_id}",
                            use_container_width=True,
                        )
                else:
                    st.warning(
                        "PDF non disponible. Le moteur Typst n'a pas pu générer le rendu. "
                        "Clique sur **Recompiler PDF** ci-dessous."
                    )

                if st.button("🔄 Recompiler le CV PDF (applique mes éditions)",
                             use_container_width=True,
                             help="Régénère le PDF en intégrant tes éditions de sections. La lettre n'est pas affectée.",
                             key=f"recomp_{job_id}"):
                    with st.spinner("Recompilation..."):
                        try:
                            result = generate_documents(
                                job, gen_cv=True, gen_letter=False, use_llm=False,
                                section_overrides=gen_state.get("section_overrides") or {},
                                photo_path=st.session_state.get("photo_path"),
                            )
                            gen_state["cv_path"] = result.get("cv_path", "")
                            cv_res = result.get("cv_result") or {}
                            if cv_res.get("cv_data"):
                                gen_state["cv_data"] = cv_res["cv_data"]
                            st.session_state[state_key] = gen_state
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Erreur : {exc}")

                if gen_state.get("section_overrides"):
                    n_over = sum(
                        len(v) if isinstance(v, dict) else (1 if v else 0)
                        for v in gen_state["section_overrides"].values()
                    )
                    st.caption(
                        f"✏️ {n_over} édition(s) en attente — clique 'Recompiler' pour les appliquer."
                    )
                    if st.button("🗑️ Effacer toutes mes éditions",
                                 use_container_width=True,
                                 key=f"clear_overrides_{job_id}"):
                        gen_state["section_overrides"] = {}
                        gen_state.pop("section_proposal", None)
                        
                        # [UX OPTIMIZATION] Auto-recompile to reset PDF to original LLM generation
                        with st.spinner("Restauration du CV original..."):
                            try:
                                result = generate_documents(
                                    job, gen_cv=True, gen_letter=False, use_llm=False,
                                    section_overrides={},
                                    photo_path=st.session_state.get("photo_path"),
                                )
                                gen_state["cv_path"] = result.get("cv_path", "")
                                cv_res = result.get("cv_result") or {}
                                if cv_res.get("cv_data"):
                                    gen_state["cv_data"] = cv_res["cv_data"]
                            except Exception as exc:
                                st.error(f"Erreur de restauration : {exc}")

                        st.session_state[state_key] = gen_state
                        st.rerun()

            # ───── COLONNE DROITE : ÉDITION SECTION PAR SECTION ────
            with edit_col:
                _render_section_editor(job, profile, gen_state, state_key, job_id)

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
                    # Préférer le PDF si disponible, sinon fallback texte
                    lp = gen_state.get("letter_path", "")
                    if lp and Path(lp).exists() and lp.endswith(".pdf"):
                        with open(lp, "rb") as _lf:
                            st.download_button(
                                "✉️ Télécharger lettre (.pdf)",
                                data=_lf.read(),
                                file_name=f"Lettre_{safe_filename(job.get('company','job'))}.pdf",
                                mime="application/pdf", use_container_width=True,
                                key=f"dl_lt_{job_id}",
                            )
                    else:
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
                        save_final_candidate_version(
                            job_id=job_id,
                            job=job,
                            gen_state=gen_state,
                            photo_path=st.session_state.get("photo_path"),
                            persona=st.session_state.get("selected_persona", "Industrial"),
                        )
                        st.session_state[state_key] = gen_state
                        st.success("⭐ Version finale archivée.")
                        st.rerun()
                    except Exception as exc:
                        _logger.exception(
                            "Erreur lors de la validation finale — job_id=%s", job_id
                        )
                        st.error(f"Erreur : {exc}")

            # ───── MARQUER COMME ENVOYÉ ────────────────────────
            if st.button("📤 J'ai postulé — clore la candidature",
                         use_container_width=True,
                         key=f"sent_{job_id}"):
                try:
                    mark_application_as_sent(job_id=job_id, gen_state=gen_state)
                except Exception as exc:
                    _logger.exception(
                        "Erreur lors du marquage envoyé — job_id=%s", job_id
                    )
                    st.error(f"Erreur : {exc}")
                else:
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
                            f"<div style='font-size:0.78rem;color:var(--text-muted);'>"
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
                            f"<div style='font-size:0.78rem;color:var(--text-muted);'>"
                            f"v{v['version']}{flag} · {v.get('created_at','')[:16]}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # === ONGLET 3 : COMPARE VIEW (Persona Duel) =================
    with tab_compare:
        if not gen_state.get("duel_industrial") and not gen_state.get("duel_research"):
            st.info("Le mode Duel n'est pas activé. Clique sur '🌓 Generate Both (Persona Duel)' dans l'onglet Studio pour comparer deux versions.")
        else:
            st.markdown("#### 🌓 Persona Duel : Industrial vs Research")
            st.caption("Fais défiler les deux versions et clique sur celle que tu souhaites conserver.")
            
            # Retrieve data for both
            ind = gen_state.get("duel_industrial") or {}
            res = gen_state.get("duel_research") or {}
            
            p_ind = ind.get("cv_path")
            p_res = res.get("cv_path")
            
            duel_col1, duel_col2 = st.columns(2)
            
            with duel_col1:
                st.markdown("##### ⚙️ Version Industrielle")
                if p_ind and Path(p_ind).exists():
                    render_pdf_viewer(p_ind, height=800)
                    if st.button("🏆 Keep Industrial", key=f"keep_ind_{job_id}", type="primary", use_container_width=True):
                        gen_state.update(ind)
                        gen_state["selected_persona"] = "Industrial"
                        gen_state["is_duel_mode"] = False
                        st.session_state[state_key] = gen_state
                        st.success("✅ Version Industrielle conservée !")
                        st.rerun()
                else:
                    st.warning("Version Industrielle non disponible.")
                    
            with duel_col2:
                st.markdown("##### 🔬 Version Recherche")
                if p_res and Path(p_res).exists():
                    render_pdf_viewer(p_res, height=800)
                    if st.button("🏆 Keep Research", key=f"keep_res_{job_id}", type="primary", use_container_width=True):
                        gen_state.update(res)
                        gen_state["selected_persona"] = "Research"
                        gen_state["is_duel_mode"] = False
                        st.session_state[state_key] = gen_state
                        st.success("✅ Version Recherche conservée !")
                        st.rerun()
                else:
                    st.warning("Version Recherche non disponible.")

    # === ONGLET 4 : SKILL CLOUD =================================
    with tab_skills:
        from engine.studio_analysis import render_skill_cloud
        st.markdown("#### ☁️ Skill Cloud Analysis")
        st.caption("Visualisation sémantique des compétences de l'offre vs ton profil.")
        st.components.v1.html(render_skill_cloud(profile, job), height=500)



# ─── HERO ────────────────────────────────────────────────────────
stats = db.get_stats()

st.markdown(
    "<div class=\"hero-container\">"
    "<div class=\"hero-h1\">Studio de Candidature</div>"
    "<div class=\"hero-h2\">"
    "Sélectionne une offre, prépare ta candidature en un clic, "
    "édite le contenu, télécharge et envoie. Tout sur une seule page."
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)

# 🧬 Persona Toggle (Instant Reframing)
# We use a columns layout for the toggle to keep it clean
c_persona, c_empty = st.columns([1, 1])
with c_persona:
    persona_options = {
        "🔬 Research": "Research",
        "⚙️ Industrial": "Industrial",
        "🚀 Startup": "Startup"
    }
    
    # Segmented Control avec icônes
    selected_label = st.segmented_control(
        "**Persona de Candidature (Instant Reframing)**",
        options=list(persona_options.keys()),
        default=next(k for k, v in persona_options.items() if v == st.session_state["selected_persona"]),
        help="Change le 'vibe' et le vocabulaire du CV généré par l'IA.",
        key="persona_toggle_segmented"
    )
    
    # Mise à jour immédiate si changement
    if selected_label:
        new_persona = persona_options[selected_label]
        if new_persona != st.session_state["selected_persona"]:
            st.session_state["selected_persona"] = new_persona
            st.rerun()
    
    # 👻 "Ghost Preview" (The Narrative Sneak Peek)
    persona_goals = {
        "Research": "Focusing on FEA methodology, peer-reviewed accuracy, and academic rigor.",
        "Industrial": "Focusing on production standards, industrial efficiency, and technical robustness.",
        "Startup": "Focusing on fast prototyping, Python versatility, and R&D agility."
    }
    current_goal = persona_goals.get(st.session_state["selected_persona"], "")
    
    st.markdown(
        f"""
        <div class="ghost-preview">
            <div class="ghost-label">🎯 Narrative Goal</div>
            <div class="ghost-text">{current_goal}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# KPIs
k1, k2, k3, k4 = st.columns(4)
k1.metric("Offres", stats["total"])
k2.metric("Envoyées", stats["sent"])
k3.metric("Entretiens", stats["interviews"])
k4.metric("Offres reçues", stats["offers"])

# 📈 PERFORMANCE ANALYTICS
with st.expander("📈 Voir l'Analyse de Performance (Conversion Funnel)", expanded=False):
    from engine.analytics import AnalyticsEngine
    analytics = AnalyticsEngine(db)
    
    funnel = analytics.get_funnel_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"### {funnel['response_rate']}%")
        st.caption("Taux de réponse (Entretiens / Envois)")
        st.progress(funnel['response_rate'] / 100 if funnel['response_rate'] <= 100 else 1.0)
    with col2:
        st.markdown(f"### {funnel['offer_rate']}%")
        st.caption("Taux de succès (Offres / Entretiens)")
        st.progress(funnel['offer_rate'] / 100 if funnel['offer_rate'] <= 100 else 1.0)
    with col3:
        if st.button("📥 Exporter tracker.csv", use_container_width=True):
            csv_path = analytics.export_to_csv()
            st.success(f"✅ Tracker exporté : {csv_path}")
            with open(csv_path, "rb") as f:
                st.download_button("⬇️ Télécharger le CSV", f, file_name="tracker.csv", mime="text/csv", key="dl_tracker_csv")

    st.divider()
    
    perf_col1, perf_col2 = st.columns(2)
    
    with perf_col1:
        st.markdown("#### 🎯 Performance par Headline")
        headline_perf = analytics.get_headline_performance()
        if not headline_perf.empty:
            st.dataframe(
                headline_perf,
                column_config={
                    "headline_clean": "Accroche",
                    "sent": "Envois",
                    "interviews": "🎤",
                    "offers": "🎉",
                    "response_rate": st.column_config.ProgressColumn("Réponse", format="%f%%", min_value=0, max_value=100)
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Pas assez de données pour l'analyse des accroches.")

    with perf_col2:
        st.markdown("#### 🤖 Performance par Modèle IA")
        model_perf = analytics.get_model_performance()
        if not model_perf.empty:
            st.dataframe(
                model_perf,
                column_config={
                    "generation_model": "Modèle",
                    "sent": "Envois",
                    "interviews": "🎤",
                    "offers": "🎉",
                    "response_rate": st.column_config.ProgressColumn("Réponse", format="%f%%", min_value=0, max_value=100)
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Pas assez de données pour l'analyse des modèles.")

# ═══════════════════════════════════════════════════════════════
# SECTION 0 — RECHERCHE AUTOMATIQUE & AJOUT MANUEL
# ═══════════════════════════════════════════════════════════════
st.markdown("<div class='section-card'>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>⓪ ALIMENTATION DU PIPELINE</div>", unsafe_allow_html=True)
st.markdown("<div class='section-h2'>Trouver de nouvelles offres</div>", unsafe_allow_html=True)

tab_auto, tab_manual = st.tabs(["🤖 Recherche automatique", "✍️ Ajouter une offre manuellement"])

# ─── TAB 1 : MOTEUR FRANCE-FIRST (3 sources officielles) ─────────
with tab_auto:
    import threading
    import time as _time

    try:
        import yaml as _yaml
        _cfg = _yaml.safe_load(open(ROOT / "profiles" / "search_config.yaml", encoding="utf-8")) or {}
    except Exception:
        _cfg = {}
    try:
        _targets = _yaml.safe_load(open(ROOT / "profiles" / "target_companies.yaml", encoding="utf-8")) or {}
    except Exception:
        _targets = {}

    dept_options = (_cfg.get("search", {}) or {}).get("departments_options") or []
    employer_categories = _targets.get("categories") or []
    base_keywords = (_cfg.get("search", {}) or {}).get("keywords") or []

    # État des credentials (juste pour l'info utilisateur)
    from engine.sourcing import adzuna as _adz
    from engine.sourcing import france_travail as _ft
    ft_ok = _ft.has_credentials()
    adz_ok = _adz.has_credentials()
    has_gem = bool(os.getenv("GEMINI_API_KEY"))

    # ── En-tête : statut des sources ────────────────────────────
    st.markdown(
        "Moteur **France-First** : 3 sources stables et officielles, "
        "spécialement adaptées au profil Simulation / R&D / Énergie en France."
    )
    s1, s2, s3 = st.columns(3)
    with s1:
        if not ft_ok:
            st.warning("🇫🇷 **France Travail**\nClés manquantes (`FT_CLIENT_ID`, `FT_CLIENT_SECRET`)")
        use_ft = st.toggle("🇫🇷 Activer France Travail", value=ft_ok, disabled=not ft_ok, key="tg_ft")
    with s2:
        if not adz_ok:
            st.warning("🌍 **Adzuna**\nClés manquantes (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`)")
        use_adz = st.toggle("🌍 Activer Adzuna", value=adz_ok, disabled=not adz_ok, key="tg_adz")
    with s3:
        use_cw = st.toggle(f"🎯 Activer Companies Watcher", value=True, key="tg_cw")
        st.caption(f"{len(_targets.get('companies', []))} employeurs surveillés")

    st.divider()

    # ── Profil cible (oriente les mots-clés et le scoring) ───────
    from engine.sourcing.orchestrator import list_target_profiles
    available_profiles = list_target_profiles()
    if available_profiles:
        profile_keys = [p["key"] for p in available_profiles]
        profile_labels = {p["key"]: p["headline"] for p in available_profiles}
        sel_profile = st.selectbox(
            "👤 Profil cible (oriente mots-clés et scoring)",
            options=["(aucun — config par défaut)"] + profile_keys,
            format_func=lambda k: k if k.startswith("(") else profile_labels.get(k, k),
            key="auto_profile",
            help="Choisis l'angle du profil que tu veux mettre en avant. "
                 "Les mots-clés du profil sont utilisés en priorité dans la recherche.",
        )
        sel_profile_key = None if sel_profile.startswith("(") else sel_profile
    else:
        sel_profile_key = None

    # ── Sélection : départements + catégories ────────────────────
    sel1, sel2 = st.columns(2)
    with sel1:
        dept_labels = [d["label"] for d in dept_options]
        sel_dept_labels = st.multiselect(
            "📍 Départements ciblés (France Travail)",
            options=dept_labels,
            default=[],
            help="Laisse vide pour une recherche nationale.",
            key="auto_depts",
        )
        sel_dept_codes = [d["code"] for d in dept_options if d["label"] in sel_dept_labels]
    with sel2:
        cat_labels = {c["id"]: f"{c.get('emoji','')} {c['label']}" for c in employer_categories}
        sel_cat_ids = st.multiselect(
            "🎯 Catégories d'employeurs cibles (Companies Watcher)",
            options=list(cat_labels.keys()),
            format_func=lambda x: cat_labels.get(x, x),
            default=list(cat_labels.keys()),
            help="Surveillance active des pages carrières via leurs APIs ATS publiques.",
            key="auto_cats",
        )

    extra_kw_text = st.text_area(
        "Mots-clés additionnels (un par ligne, optionnel)",
        value="",
        placeholder="Ajoute des mots-clés ciblés pour Adzuna et Companies Watcher.\n"
                    "Exemple :\nIngénieur jumeau numérique\nIngénieur thermique procédés",
        height=80,
        key="auto_extra_kw",
    )

    # ── Toggles IA ───────────────────────────────────────────────
    st.markdown("##### 🧠 Enrichissement IA (Gemini)")
    ai1, ai2, ai3 = st.columns(3)
    with ai1:
        use_expansion = st.toggle(
            "💡 Expansion sémantique", value=has_gem, key="ai_exp", disabled=not has_gem,
            help="Gemini génère des variantes des mots-clés (synonymes, intitulés équivalents).",
        )
    with ai2:
        use_rerank = st.toggle(
            "🧠 Re-classement IA", value=has_gem, key="ai_rerank", disabled=not has_gem,
            help="Gemini évalue le fit profond de chaque top candidat (score + raisonnement).",
        )
    with ai3:
        use_skills = st.toggle(
            "🔍 Extraction compétences", value=has_gem, key="ai_skills", disabled=not has_gem,
            help="Gemini extrait les compétences clés depuis chaque description.",
        )
    if not has_gem:
        st.caption("ℹ️ Ajoute `GEMINI_API_KEY` dans Secrets pour activer l'enrichissement IA.")

    # ── Pattern asynchrone (ThreadPoolExecutor + stop_event) ─────
    if "search_state" not in st.session_state:
        st.session_state["search_state"] = "idle"
    if "bulk_selected" not in st.session_state:
        st.session_state["bulk_selected"] = set()
    if "bulk_selected_arch" not in st.session_state:
        st.session_state["bulk_selected_arch"] = set()
    search_state = st.session_state["search_state"]

    if search_state == "idle":
        launch = st.button(
            "🚀 Trouver mes offres", type="primary",
            use_container_width=True, key="btn_auto_scan",
        )
        if launch:
            extra_kw = [k.strip() for k in extra_kw_text.splitlines() if k.strip()]

            from engine.sourcing.orchestrator import scan_jobs

            stop_event = threading.Event()
            progress_box = {"p": 0.0, "msg": "Initialisation…"}

            def _cb(p: float, msg: str):
                progress_box["p"] = min(max(p, 0.0), 1.0)
                progress_box["msg"] = msg

            def _runner():
                try:
                    return scan_jobs(
                        selected_categories=sel_cat_ids or None,
                        departments=sel_dept_codes or None,
                        extra_keywords=extra_kw or None,
                        target_profile=sel_profile_key,
                        use_llm_expansion=use_expansion,
                        use_llm_rerank=use_rerank,
                        use_llm_skills=use_skills,
                        enable_france_travail=use_ft,
                        enable_adzuna=use_adz,
                        enable_companies_watcher=use_cw,
                        progress_callback=_cb,
                        should_stop=stop_event.is_set,
                    )
                except Exception as exc:
                    return {"__error__": True, "msg": str(exc)}

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

        st.progress(progress_box["p"], text=progress_box["msg"])

        bcol1, bcol2 = st.columns([1, 1])
        with bcol1:
            if st.button("⏸️ Annuler la recherche", type="secondary",
                         use_container_width=True, key="btn_stop_search"):
                if stop_event:
                    stop_event.set()
                st.toast("⏸️ Arrêt demandé… les offres collectées seront conservées.")
        with bcol2:
            st.caption("Recherche en arrière-plan · 30-60 s typiquement.")

        if future is not None and future.done():
            try:
                result = future.result()
            except Exception as exc:
                result = {"__error__": True, "msg": str(exc)}

            executor = st.session_state.get("search_executor")
            if executor:
                try: executor.shutdown(wait=False)
                except Exception: pass

            for k in ("search_future", "search_executor", "search_stop_event", "search_progress"):
                st.session_state.pop(k, None)

            if isinstance(result, dict) and result.get("__error__"):
                st.error(f"❌ Erreur durant la recherche : {result.get('msg','inconnue')}")
            else:
                jobs = result.get("jobs", []) if isinstance(result, dict) else []
                by_source = result.get("by_source", {}) if isinstance(result, dict) else {}
                warnings = result.get("warnings", []) if isinstance(result, dict) else []
                summary = result.get("summary", "") if isinstance(result, dict) else ""

                added = db.upsert_jobs(jobs) if jobs else 0
                stopped = bool(stop_event and stop_event.is_set())

                if stopped:
                    st.warning(
                        f"⏸️ Recherche interrompue · {len(jobs)} offres collectées · "
                        f"**{added} nouvelles** ajoutées."
                    )
                else:
                    st.success(
                        f"✅ {summary} · **{added} nouvelles** ajoutées au pipeline."
                    )
                # Détail par source
                if by_source:
                    parts = []
                    icons = {"france_travail": "🇫🇷", "adzuna": "🌍", "companies_watcher": "🎯"}
                    for src, n in by_source.items():
                        parts.append(f"{icons.get(src,'•')} {src.replace('_',' ')} : **{n}**")
                    st.caption(" · ".join(parts))
                # Warnings (clés manquantes etc.)
                for w in warnings:
                    st.info(w)

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
    # --- ANALYSE INSTANTANÉE (KEYWORD GAP) ---
    m_desc = st.text_area(
        "Description / annonce complète", height=220,
        placeholder="Colle ici la description complète de l'offre — l'analyse sémantique s'affichera instantanément.",
        key="manual_job_desc"
    )

    if m_desc.strip():
        with st.expander("🔍 **Analyse Flash : Keyword Gap**", expanded=True):
            from engine.cv_generator import PersonalCVGenerator
            from engine.studio_analysis import analyze_keyword_gap
            
            # Initialisation légère du moteur (cache-friendly)
            @st.cache_resource
            def get_fast_generator():
                return PersonalCVGenerator()
            
            gen = get_fast_generator()
            profile = load_profile()
            
            with st.spinner("Analyse des compétences..."):
                gap = run_coroutine_sync(analyze_keyword_gap(m_desc, profile, llm=gen.llm))
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### ✅ Found")
                if gap["matched"]:
                    for s in gap["matched"]:
                        st.markdown(f"- <span style='color:#10b981;font-weight:600;'>{s.capitalize()}</span>", unsafe_allow_html=True)
                else:
                    st.caption("Aucun match direct détecté.")
            with c2:
                st.markdown("##### ⚠️ Missing")
                if gap["missing"]:
                    for s in gap["missing"]:
                        st.markdown(f"- <span style='color:#ef4444;font-weight:600;'>{s.capitalize()}</span>", unsafe_allow_html=True)
                else:
                    st.success("Toutes les compétences clés semblent couvertes !")
            
            st.info("💡 **Conseil :** Si des compétences critiques sont 'Missing', ajoute-les à ton profil (Section ④) avant de générer le CV.")

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

# Par défaut : aucune source pré-sélectionnée → toutes les offres sont visibles
default_sources: list[str] = []

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
    turbo_mode = st.toggle("⚡ Turbo Mode (Bulk Actions)", value=False, key="turbo_match")
with cb2:
    selected_sources = st.multiselect(
        "🔗 Sources",
        options=all_sources,
        default=default_sources,
        help="Laisse vide pour voir toutes les sources. Sélectionne une ou plusieurs sources pour filtrer.",
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
    
    if turbo_mode:
        st.markdown("<div class='bulk-actions-bar'>", unsafe_allow_html=True)
        tcol1, tcol2, tcol3 = st.columns([1.2, 1, 2.5])
        with tcol1:
            if st.button("✅ Select All (Top 5)", use_container_width=True, key="bulk_sel_all"):
                st.session_state["bulk_selected"] = {j["id"] for j in smart_jobs[:5]}
                st.rerun()
        with tcol2:
            if st.button("❌ Clear All", use_container_width=True, key="bulk_clear_all"):
                st.session_state["bulk_selected"] = set()
                st.rerun()
        with tcol3:
            selected_count = len(st.session_state["bulk_selected"])
            btn_label = f"🚀 Bulk Generate ({selected_count}/5)"
            if st.button(btn_label, type="primary", use_container_width=True, 
                         disabled=selected_count == 0 or selected_count > 5,
                         key="bulk_gen_run"):
                # Logic for bulk generation
                progress_text = "Génération en masse..."
                my_bar = st.progress(0, text=progress_text)
                selected_ids = list(st.session_state["bulk_selected"])
                for i, jid in enumerate(selected_ids):
                    target_job = next((job for job in smart_jobs if job["id"] == jid), None)
                    if target_job:
                        my_bar.progress((i + 1) / len(selected_ids), text=f"Génération {i+1}/{len(selected_ids)} : {target_job.get('title','')}")
                        try:
                            generate_documents(
                                target_job, 
                                gen_cv=True, 
                                gen_letter=True, 
                                use_llm=True,
                                persona=st.session_state.get("selected_persona", "Industrial"),
                                photo_path=st.session_state.get("photo_path")
                            )
                            db.update_status(jid, "generated", target_job.get("notes", ""))
                        except Exception as e:
                            st.error(f"Erreur pour {target_job.get('title','')}: {e}")
                my_bar.empty()
                st.session_state["bulk_selected"] = set()
                st.success(f"✅ {len(selected_ids)} candidatures générées avec succès !")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

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
        if turbo_mode:
            c_sel, c_info, c_del = st.columns([0.6, 5.4, 0.8])
            with c_sel:
                is_selected = j["id"] in st.session_state["bulk_selected"]
                if st.checkbox("", value=is_selected, key=f"chk_bulk_{j['id']}", label_visibility="collapsed"):
                    st.session_state["bulk_selected"].add(j["id"])
                else:
                    st.session_state["bulk_selected"].discard(j["id"])
        else:
            c_info, c_btn, c_del = st.columns([5, 1.2, 0.8])
        
        with c_info:
            is_ghost = "👻 " if "Ghost-Sourced" in (j.get("notes") or "") else ""
            row_html = (
                "<div class='row-card'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;gap:12px;'>"
                "<div style='flex:1;'>"
                f"<div class='row-title'>{is_ghost}{j.get('title','')}</div>"
                "<div class='row-meta'>"
                f"{j.get('company','?')} — {j.get('location','?')}"
                f" &nbsp;·&nbsp; 📅 <b>{sourcing}</b>"
                f"{ai_badge}"
                "</div>"
                # --- GHOST BENEFITS (Remote/Salary) ---
                f"{render_ghost_badges(j)}"
                f"{ai_line}"
                f"{render_status_pipeline(j)}"
                "</div>"
                f"<span class='score-pill {score_class(score)}'>{score}%</span>"
                "</div>"
                "</div>"
            )
            st.markdown(row_html, unsafe_allow_html=True)
            
            # 🗺️ Ripple Search (Golden Jobs)
            if score >= GOLDEN_THRESHOLD:
                r_key = f"ripple_{j['id']}"
                if r_key not in st.session_state:
                    st.session_state[r_key] = None
                
                if st.session_state[r_key]:
                    st.markdown(render_ripple_results(st.session_state[r_key]), unsafe_allow_html=True)
                else:
                    if st.button("🗺️ Search Competitors", key=f"btn_ripple_{j['id']}", 
                                 help="Find top 5 competitors in this sector and their career pages"):
                        with st.spinner("Analyzing industrial sector and ripples..."):
                            engine = RippleEngine()
                            results = run_coroutine_sync(
                                engine.identify_competitors(j.get("company", ""), j.get("title", "")),
                                context="ripple_search"
                            )
                            st.session_state[r_key] = results
                        st.rerun()
        if not turbo_mode:
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

turbo_archive = st.toggle("⚡ Turbo Mode (Bulk Actions)", value=False, key="turbo_arch")

sent_jobs = db.get_jobs(status="sent", limit=200)

if not sent_jobs:
    st.info("Aucune candidature envoyée pour le moment. Prépare et envoie ta première via le Studio ci-dessus.")
else:
    st.caption(f"{len(sent_jobs)} candidature(s) envoyée(s)")
    
    if turbo_archive:
        st.markdown("<div class='bulk-actions-bar'>", unsafe_allow_html=True)
        tcol1, tcol2, tcol3 = st.columns([1.2, 1, 2.5])
        with tcol1:
            if st.button("✅ Select All (Top 5)", use_container_width=True, key="bulk_sel_all_arch"):
                st.session_state["bulk_selected_arch"] = {j["id"] for j in sent_jobs[:5]}
                st.rerun()
        with tcol2:
            if st.button("❌ Clear All", use_container_width=True, key="bulk_clear_all_arch"):
                st.session_state["bulk_selected_arch"] = set()
                st.rerun()
        with tcol3:
            selected_count = len(st.session_state["bulk_selected_arch"])
            btn_label = f"🚀 Bulk Generate ({selected_count}/5)"
            if st.button(btn_label, type="primary", use_container_width=True, 
                         disabled=selected_count == 0 or selected_count > 5,
                         key="bulk_gen_run_arch"):
                progress_text = "Génération en masse..."
                my_bar = st.progress(0, text=progress_text)
                selected_ids = list(st.session_state["bulk_selected_arch"])
                for i, jid in enumerate(selected_ids):
                    target_job = next((job for job in sent_jobs if job["id"] == jid), None)
                    if target_job:
                        my_bar.progress((i + 1) / len(selected_ids), text=f"Génération {i+1}/{len(selected_ids)} : {target_job.get('title','')}")
                        try:
                            generate_documents(
                                target_job, 
                                gen_cv=True, 
                                gen_letter=True, 
                                use_llm=True,
                                persona=st.session_state.get("selected_persona", "Industrial"),
                                photo_path=st.session_state.get("photo_path")
                            )
                        except Exception as e:
                            st.error(f"Erreur pour {target_job.get('title','')}: {e}")
                my_bar.empty()
                st.session_state["bulk_selected_arch"] = set()
                st.success(f"✅ {len(selected_ids)} candidatures régénérées avec succès !")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    for j in sent_jobs:
        with st.container():
            if turbo_archive:
                c_sel, c_top, c_actions = st.columns([0.6, 3.4, 2.5])
                with c_sel:
                    is_selected = j["id"] in st.session_state["bulk_selected_arch"]
                    if st.checkbox("", value=is_selected, key=f"chk_arch_{j['id']}", label_visibility="collapsed"):
                        st.session_state["bulk_selected_arch"].add(j["id"])
                    else:
                        st.session_state["bulk_selected_arch"].discard(j["id"])
                top = c_top
                actions = c_actions
            else:
                top, actions = st.columns([4, 2.5])
            
            with top:
                sourcing = (j.get("sourcing_date") or "")[:10] or "—"
                sent_at = j.get("sent_at") or j.get("applied_date") or "—"
                arch_html = (
                    "<div class='row-card'>"
                    f"<div class='row-title'>{j.get('title','')}</div>"
                    "<div class='row-meta'>"
                    f"🏢 {j.get('company','?')} — 📍 {j.get('location','?')}<br/>"
                    f"📅 Découverte le <b>{sourcing}</b>"
                    f" &nbsp;·&nbsp; 📤 Envoyé le <b>{sent_at}</b>"
                    f" &nbsp;·&nbsp; via <b>{j.get('sent_via') or 'manual'}</b>"
                    "</div>"
                    "</div>"
                )
                st.markdown(arch_html, unsafe_allow_html=True)
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
                        lt_ext = Path(letter_path).suffix
                        lt_mime = "application/pdf" if lt_ext == ".pdf" else "text/plain"
                        with open(letter_path, "rb") as f:
                            st.download_button(
                                "✉️ Lettre", data=f.read(),
                                file_name=f"Lettre_{safe_filename(j.get('company',''))}{lt_ext}",
                                mime=lt_mime, use_container_width=True,
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

PROFILE_PATH = ROOT / "profiles" / "master_profile.json"
history_manager = ProfileHistory(PROFILE_PATH)


def _load_profile() -> dict:
    if PROFILE_PATH.exists():
        try:
            return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_profile(data: dict) -> None:
    history_manager.save_with_history(data)


prof = _load_profile()
pi = prof.setdefault("personal_info", {})

# ─── PHOTO DE PROFIL ────────────────────────────────────────────
st.subheader("📸 Photo de profil")
col_photo, col_info = st.columns([1, 2])
with col_photo:
    current_photo = st.session_state.get("photo_path")
    if current_photo and Path(current_photo).exists():
        st.image(current_photo, width=150, caption="Photo actuelle")
    else:
        st.markdown("_(aucune photo)_")
with col_info:
    uploaded = st.file_uploader(
        "Uploader ta photo (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        key="photo_uploader",
    )
    if uploaded:
        import tempfile
        suffix = Path(uploaded.name).suffix or ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded.read())
        tmp.flush()
        st.session_state["photo_path"] = tmp.name
        st.success(f"✅ Photo enregistrée ({uploaded.name})")
        st.image(tmp.name, width=150)

st.divider()

p_tab1, p_tab2, p_tab3, p_tab4, p_tab5, p_tab6 = st.tabs([
    "👤 Identité", "🎓 Formation", "💼 Expériences",
    "🛠️ Compétences", "📦 JSON brut", "🛡️ Historique",
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

# ─── HISTORIQUE ────────────────────────────────────────────────
with p_tab6:
    st.caption("🛡️ Career Versioning : Sauvegardes automatiques et snapshots Git.")
    snapshots = history_manager.list_snapshots()
    if not snapshots:
        st.info("Aucun historique pour le moment. Modifie ton profil pour créer un snapshot.")
    else:
        for snap in snapshots[:15]: # Show last 15
            with st.container():
                sc1, sc2 = st.columns([3, 1])
                with sc1:
                    st.markdown(f"📄 `{snap.name}`")
                    st.caption(f"Date : {datetime.fromtimestamp(snap.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                with sc2:
                    if st.button("Restaurer", key=f"restore_{snap.name}"):
                        try:
                            content = json.loads(snap.read_text(encoding="utf-8"))
                            _save_profile(content)
                            st.success(f"✅ Profil restauré depuis {snap.name}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur de restauration : {e}")

st.markdown("</div>", unsafe_allow_html=True)

st.caption("© Job Copilot · Studio de Candidature · Zein ELAJAMY — ENSEM 2026")
