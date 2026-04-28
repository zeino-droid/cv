#!/usr/bin/env python3
"""
🚀 BATCH APPLY — Pipeline de candidature massive
Génère CV + lettre + tracker pour des offres ciblées.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from engine import matching

OUTPUT_DIR = Path("vault")
TRACKER_FILE = Path("storage/tracker.csv")
TRACKER_HEADERS = [
    "id", "company", "title", "location", "score", "source",
    "cv_path", "letter_path", "url", "status",
    "generated_date", "applied_date", "response_date", "notes",
]

# ──────────────────────────────────────────────────────────────
# Helpers texte
# ──────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    value = str(text or "").replace("\r", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _safe_duration(start_date: str, end_date: str) -> str:
    if not start_date or not end_date:
        return ""

    def _year(value: str) -> Optional[int]:
        value = value.strip().lower()
        if not value:
            return None
        if "présent" in value or "present" in value:
            return datetime.now().year
        try:
            if "/" in value:
                return int(value.split("/")[-1])
            return int(value[:4])
        except Exception:
            return None

    start_year = _year(start_date)
    end_year = _year(end_date)
    if start_year is None or end_year is None:
        return ""

    years = max(0, end_year - start_year)
    if years <= 0:
        return "une expérience récente"
    if years == 1:
        return "1 an d'expérience"
    return f"{years} ans d'expérience"


def _job_focus_terms(job: Dict) -> str:
    terms: List[str] = []
    for source in (job.get("matched_skills", []) or [], job.get("required_skills", []) or []):
        for item in source:
            clean = _clean_text(item)
            if clean and clean not in terms:
                terms.append(clean)
    return ", ".join(terms[:5]) if terms else "simulation numérique, modélisation, Python"


def _experience_summary(profile: Dict) -> str:
    experiences = profile.get("experience_stark", [])
    if not experiences:
        return "Mon parcours m'a permis de développer une expertise solide en ingénierie et en simulation."

    main_exp = experiences[0]
    company = _clean_text(main_exp.get("company", ""))
    period = main_exp.get("period", "")
    start_date = period.split("-")[0].strip() if "-" in period else period
    end_date = period.split("-")[-1].strip() if "-" in period else ""
    
    duration = _safe_duration(start_date, end_date)

    if company and duration:
        return f"J'ai développé mon expérience au sein de {company} pendant {duration}."
    if company:
        return f"J'ai développé mon expérience au sein de {company}."
    if duration:
        return f"J'ai développé {duration} d'expérience en environnement industriel."
    return "Mon parcours m'a permis de développer une expertise solide en ingénierie et en simulation."


def _sanitize_letter(letter: str) -> str:
    cleaned = _clean_text(letter)
    replacements = {
        "3 ans d'expérience": "",
        "3 ans": "",
        "ArcelorMittal R&D": "ArcelorMittal",
        "chez  ": "chez ",
        "de  ": "de ",
        "au sein de  ": "au sein de ",
        "  ": " ",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


# ──────────────────────────────────────────────────────────────
# Lettre de motivation
# ──────────────────────────────────────────────────────────────

def generate_cover_letter_heuristic(profile: Dict, job: Dict) -> str:
    personal_info = profile.get("personal_info", {})
    name = _clean_text(personal_info.get("name", "Candidat"))
    email = _clean_text(personal_info.get("email", ""))
    phone = _clean_text(personal_info.get("phone", ""))
    location = _clean_text(personal_info.get("location", "France"))

    education = profile.get("education", [])
    main_edu = education[0] if education else {}
    school = _clean_text(main_edu.get("institution", ""))
    degree = _clean_text(main_edu.get("degree", "Diplôme d'ingénieur"))
    school_short = school.split("(")[0].strip() if school else "école d'ingénieurs"

    summary = _clean_text(personal_info.get("summary_default", "")) or (
        "Mon parcours m'a permis de développer une expertise solide en ingénierie et en simulation."
    )

    job_title = _clean_text(job.get("title", "le poste proposé"))
    company = _clean_text(job.get("company", "votre entreprise"))
    skills_str = _job_focus_terms(job)
    exp_summary = _experience_summary(profile)
    today = datetime.now().strftime("%d/%m/%Y")

    experiences = profile.get("experience_stark", [])
    required_terms = [
        _clean_text(s).lower() for s in (job.get("required_skills", []) or []) if _clean_text(s)
    ]
    top_achievements: List[str] = []
    for exp in experiences:
        tech_str = " ".join(_clean_text(t).lower() for t in exp.get("K", []))
        achievements = exp.get("A", [])
        if isinstance(achievements, str): achievements = [achievements]
        for ach in achievements[:4]:
            ach_clean = _clean_text(ach).lstrip("•-– ").strip()
            if not ach_clean:
                continue
            if not required_terms or any(
                term in ach_clean.lower() or term in tech_str for term in required_terms[:3]
            ):
                top_achievements.append(ach_clean)
    top_achievements = top_achievements[:2]

    lines = [
        name,
        email,
        phone,
        location,
        "",
        today,
        "",
        f"Objet : Candidature au poste de {job_title}",
        "",
        "Madame, Monsieur,",
        "",
        f"Je vous adresse ma candidature pour le poste de {job_title} au sein de {company}.",
        "",
        exp_summary,
        "",
        f"Je souhaite mettre à profit mes compétences en {skills_str}.",
        "",
        summary,
    ]

    if top_achievements:
        lines += ["", "Parmi mes réalisations concrètes :"]
        lines.extend(f"• {ach}" for ach in top_achievements)

    lines += [
        "",
        f"Ces compétences, combinées à ma formation d'ingénieur ({degree} — {school_short}), me permettent d'apporter une contribution immédiate sur des sujets techniques complexes.",
        "",
        "Je serais ravi d'échanger avec vous afin de vous présenter plus en détail ma démarche et la valeur que je peux apporter à votre équipe.",
        "",
        "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
        "",
        name,
    ]

    letter = "\n".join(lines)
    letter = re.sub(r"\n{3,}", "\n\n", letter).strip()
    return _sanitize_letter(letter)


async def generate_cover_letter_llm(generator: Any, profile: Dict, job: Dict) -> Optional[str]:
    if not generator or not getattr(generator, "llm", None):
        return None

    personal_info = profile.get("personal_info", {})
    experiences = profile.get("experience_stark", [])
    main_exp = experiences[0] if experiences else {}
    exp_summary = (
        f"{main_exp.get('title', '')} chez {main_exp.get('company', '')}"
        if main_exp
        else ""
    )

    ach_text = ""
    top_ach = []
    for exp in experiences[:2]:
        achievements = exp.get("A", [])
        if isinstance(achievements, str): achievements = [achievements]
        for ach in achievements[:2]:
            top_ach.append(f"• {_clean_text(ach).lstrip('•-– ').strip()}")
    if top_ach:
        ach_text = "\n".join(top_ach[:3])

    prompt = f"""Tu es un expert en rédaction de lettres de motivation pour des ingénieurs en France.
    
INTERDICTION FORMELLE : N'utilise jamais les mots 'Apprenti', 'Étudiant', 'Élève'. Présente le candidat comme un expert opérationnel.

CANDIDAT: {personal_info.get("name", "Candidat")}
RÉSUMÉ: {personal_info.get("summary_default", "")}
EXPÉRIENCE PRINCIPALE: {exp_summary}
COMPÉTENCES LIÉES AU POSTE: {_job_focus_terms(job)}
RÉALISATIONS CLÉS:
{ach_text}

OFFRE CIBLÉE:
- Poste: {job.get("title", "")}
- Entreprise: {job.get("company", "")}
- Description: {str(job.get("description", ""))[:600]}

MISSION:
Rédige une lettre de motivation professionnelle en français (3-4 paragraphes).
"""

    try:
        result = await generator.llm.generate(prompt, temperature=0.35)
        if not result:
            return None
        return _sanitize_letter(result)
    except Exception:
        return None


def save_cover_letter(letter_text: str, output_dir: Path, name: str, company: str, title: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    def safe(value: str) -> str:
        return "".join(c if c.isalnum() or c in "._-" else "_" for c in value)
    filename = f"Lettre_{safe(name)}_{safe(company)}_{safe(title)}.txt"
    path = output_dir / filename
    path.write_text(_sanitize_letter(letter_text), encoding="utf-8")
    return path


def save_job_info(job: Dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "offre.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=2, ensure_ascii=False)
    return path


# ──────────────────────────────────────────────────────────────
# Tracker CSV
# ──────────────────────────────────────────────────────────────

def init_tracker() -> None:
    if not TRACKER_FILE.exists():
        TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(TRACKER_HEADERS)


def append_to_tracker(row: Dict) -> None:
    init_tracker()
    with open(TRACKER_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS)
        writer.writerow(row)


# ──────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────

async def process_single_job(
    generator: Any,
    profile: Dict,
    job: Dict,
    use_llm_letter: bool = True,
    photo_path: Optional[str] = None,
) -> Dict[str, Any]:
    company = job.get("company", "Unknown")
    title = job.get("title", "Poste")
    personal_info = profile.get("personal_info", {})
    name = personal_info.get("name", "Candidat")

    safe_dir = (
        "".join(c if c.isalnum() or c in "._- " else "_" for c in f"{company}_{title}")
        .strip()
        .replace(" ", "_")[:80]
    )
    job_output_dir = OUTPUT_DIR / safe_dir
    job_output_dir.mkdir(parents=True, exist_ok=True)

    # 1. CV Adaptation
    cv_result = await generator.generate_cv_for_job(job, photo_path=photo_path)
    
    # 2. Letter Generation
    letter_text = None
    if use_llm_letter:
        letter_text = await generate_cover_letter_llm(generator, profile, job)
    
    if not letter_text:
        letter_text = generate_cover_letter_heuristic(profile, job)
    
    letter_path = save_cover_letter(letter_text, job_output_dir, name, company, title)
    save_job_info(job, job_output_dir)

    # 3. Tracker Row
    row = {
        "id": job.get("id", "N/A"),
        "company": company,
        "title": title,
        "location": job.get("location", "France"),
        "score": job.get("fit_score", 0),
        "source": job.get("source", "manual"),
        "cv_path": cv_result.get("pdf_path") or cv_result.get("md_path", ""),
        "letter_path": str(letter_path),
        "url": job.get("url", ""),
        "status": "generated",
        "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "applied_date": "",
        "response_date": "",
        "notes": "",
    }
    append_to_tracker(row)
    return row
