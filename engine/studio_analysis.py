"""
engine/studio_analysis.py
Analyse légère Profil ↔ Offre pour le Studio de Candidature.
Aucune dépendance lourde : pur Python + HTML/CSS pour la heatmap.
"""

from __future__ import annotations
from typing import Iterable


def _flatten_skills(profile: dict) -> set[str]:
    """Récupère toutes les compétences du profil, normalisées en lowercase."""
    skills: set[str] = set()

    # Compétences déclarées sous différents formats
    for key in ("hard_skills", "soft_skills", "skills", "tools", "languages"):
        val = profile.get(key)
        if isinstance(val, list):
            skills.update(str(s).lower().strip() for s in val if s)
        elif isinstance(val, dict):
            for sub in val.values():
                if isinstance(sub, list):
                    skills.update(str(s).lower().strip() for s in sub if s)

    # Expériences (clé "K" pour les keywords STARK ou "skills")
    for exp in profile.get("experience_stark", []) or profile.get("experiences", []) or []:
        for k in exp.get("K", []) or exp.get("skills", []) or []:
            skills.add(str(k).lower().strip())

    # Formation
    for edu in profile.get("education", []) or []:
        for k in edu.get("skills", []) or []:
            skills.add(str(k).lower().strip())

    # Projets
    for proj in profile.get("projects", []) or []:
        for k in proj.get("skills", []) or proj.get("tech", []) or []:
            skills.add(str(k).lower().strip())

    skills.discard("")
    return skills


def _job_skills(job: dict) -> set[str]:
    out: set[str] = set()
    for key in ("required_skills", "matched_skills", "skills"):
        val = job.get(key)
        if isinstance(val, list):
            out.update(str(s).lower().strip() for s in val if s)
    out.discard("")
    return out


def build_skill_matrix(profile: dict, job: dict) -> dict:
    """
    Compare les compétences du profil et de l'offre.
    Retourne : matched / missing / bonus / score / total_job.
    """
    profile_skills = _flatten_skills(profile)
    job_skills = _job_skills(job)

    matched = sorted(job_skills & profile_skills)
    missing = sorted(job_skills - profile_skills)
    bonus = sorted(profile_skills - job_skills)

    return {
        "matched": matched,
        "missing": missing,
        "bonus": bonus,
        "score": int(job.get("fit_score", 0) or 0),
        "total_job": len(job_skills),
        "total_profile": len(profile_skills),
    }


def _pill(skill: str, color: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;margin:3px;padding:5px 11px;'
        f'border-radius:999px;font-size:0.78rem;font-weight:600;'
        f'color:{color};background:{bg};border:1px solid {color}55;">'
        f'{skill}</span>'
    )


def render_heatmap_html(matrix: dict) -> str:
    """Bloc HTML/CSS prêt pour st.components.v1.html — pas de dépendance externe."""
    matched_html = "".join(
        _pill(s, "#4ade80", "rgba(34,197,94,0.10)") for s in matrix["matched"]
    ) or '<span style="color:#475569;font-size:0.8rem;">Aucune détectée</span>'

    missing_html = "".join(
        _pill(s, "#f87171", "rgba(239,68,68,0.10)") for s in matrix["missing"]
    ) or '<span style="color:#4ade80;font-size:0.8rem;">Parfait match ! 🎯</span>'

    bonus_html = "".join(
        _pill(s, "#60a5fa", "rgba(96,165,250,0.10)") for s in matrix["bonus"][:14]
    ) or '<span style="color:#475569;font-size:0.8rem;">—</span>'

    score = matrix["score"]
    total = matrix["total_job"] or 1
    match_pct = round(len(matrix["matched"]) / total * 100) if total else 0

    return f"""
    <div style="font-family:'Outfit','Inter',sans-serif;color:#e2e8f0;">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px;">
        <div style="background:rgba(34,197,94,0.08);border-radius:14px;padding:14px;
                    border:1px solid rgba(34,197,94,0.25);">
          <div style="font-size:1.9rem;font-weight:800;color:#4ade80;line-height:1;">
            {len(matrix['matched'])}
          </div>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px;">Compétences matchées</div>
        </div>
        <div style="background:rgba(239,68,68,0.08);border-radius:14px;padding:14px;
                    border:1px solid rgba(239,68,68,0.25);">
          <div style="font-size:1.9rem;font-weight:800;color:#f87171;line-height:1;">
            {len(matrix['missing'])}
          </div>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px;">À combler</div>
        </div>
        <div style="background:rgba(56,189,248,0.08);border-radius:14px;padding:14px;
                    border:1px solid rgba(56,189,248,0.25);">
          <div style="font-size:1.9rem;font-weight:800;color:#38bdf8;line-height:1;">
            {score}%
          </div>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px;">
            Score Fit · {match_pct}% requis couverts
          </div>
        </div>
      </div>

      <div style="margin-bottom:14px;">
        <div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">✅ Maîtrisées</div>
        <div>{matched_html}</div>
      </div>

      <div style="margin-bottom:14px;">
        <div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">⚠️ À mentionner / Lacunes</div>
        <div>{missing_html}</div>
      </div>

      <div>
        <div style="font-size:0.72rem;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">💡 Bonus (atouts non demandés)</div>
        <div>{bonus_html}</div>
      </div>
    </div>
    """
