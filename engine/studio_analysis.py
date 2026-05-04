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

    # Compétences déclarées sous différents formats (clés racine)
    for key in ("hard_skills", "soft_skills", "skills", "tools", "languages"):
        val = profile.get(key)
        if isinstance(val, list):
            for s in val:
                if isinstance(s, dict):
                    name = s.get("name", "")
                elif s:
                    name = str(s)
                else:
                    continue
                if name:
                    skills.add(str(name).lower().strip())
        elif isinstance(val, dict):
            for sub in val.values():
                if isinstance(sub, list):
                    for s in sub:
                        if isinstance(s, dict):
                            name = s.get("name", "")
                        elif s:
                            name = str(s)
                        else:
                            continue
                        if name:
                            skills.add(str(name).lower().strip())

    # Taxonomie structurée (skills_taxonomy.hard_skills = [{name, level}, ...])
    taxonomy = profile.get("skills_taxonomy", {})
    if isinstance(taxonomy, dict):
        for tax_key in ("hard_skills", "soft_skills", "domain_knowledge"):
            tax_val = taxonomy.get(tax_key, [])
            if isinstance(tax_val, list):
                for s in tax_val:
                    if isinstance(s, dict):
                        name = s.get("name", "")
                    elif isinstance(s, str):
                        name = s
                    else:
                        continue
                    if name:
                        skills.add(str(name).lower().strip())

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
    Retourne : matched / missing / bonus / score / total_job / proofs.
    """
    profile_skills = _flatten_skills(profile)
    job_skills = _job_skills(job)

    matched = sorted(job_skills & profile_skills)
    missing = sorted(job_skills - profile_skills)
    bonus = sorted(profile_skills - job_skills)

    # --- Find Proofs for Matched Skills ---
    proofs = {}
    experiences = profile.get("experience_stark", []) or profile.get("experiences", []) or []
    
    for skill in matched:
        skill_low = skill.lower()
        for exp in experiences:
            exp_keywords = [str(k).lower() for k in (exp.get("K", []) or exp.get("skills", []))]
            if any(skill_low in kw or kw in skill_low for kw in exp_keywords):
                proofs[skill] = f"{exp.get('title')} @ {exp.get('company')}"
                break
        if skill not in proofs:
            # Fallback to taxonomy context
            taxonomy = profile.get("skills_taxonomy", {})
            for hs in taxonomy.get("hard_skills", []):
                if hs.get("name", "").lower() == skill_low:
                    proofs[skill] = hs.get("context", "Formation académique")
                    break

    return {
        "matched": matched,
        "missing": missing,
        "bonus": bonus,
        "proofs": proofs,
        "score": int(job.get("fit_score", 0) or 0),
        "total_job": len(job_skills),
        "total_profile": len(profile_skills),
    }


def _pill(skill: str, color: str, bg: str, tooltip: str | None = None) -> str:
    title_attr = f'title="Preuve : {tooltip}"' if tooltip else ""
    cursor = "cursor:help;" if tooltip else ""
    return (
        f'<span {title_attr} style="display:inline-block;margin:3px;padding:5px 11px;'
        f'border-radius:999px;font-size:0.78rem;font-weight:600;'
        f'color:{color};background:{bg};border:1px solid {color}55;{cursor}">'
        f'{skill}</span>'
    )


def render_heatmap_html(matrix: dict) -> str:
    """Bloc HTML/CSS prêt pour st.components.v1.html — pas de dépendance externe."""
    proofs = matrix.get("proofs", {})
    matched_html = "".join(
        _pill(s, "#10b981", "rgba(16,185,129,0.15)", proofs.get(s)) for s in matrix["matched"]
    ) or '<span style="color:#a1a1aa;font-size:0.8rem;">Aucune détectée</span>'

    missing_html = "".join(
        _pill(s, "#ef4444", "rgba(239,68,68,0.15)") for s in matrix["missing"]
    ) or '<span style="color:#10b981;font-size:0.8rem;">Parfait match ! 🎯</span>'

    bonus_html = "".join(
        _pill(s, "#3b82f6", "rgba(59,130,246,0.15)") for s in matrix["bonus"][:14]
    ) or '<span style="color:#a1a1aa;font-size:0.8rem;">—</span>'

    score = matrix["score"]
    total = matrix["total_job"] or 1
    match_pct = round(len(matrix["matched"]) / total * 100) if total else 0

    return f"""
    <div style="font-family:'Outfit','Inter',sans-serif;color:#ededed;">
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px;">
        <div style="background:rgba(16,185,129,0.10);border-radius:14px;padding:14px;
                    border:1px solid rgba(16,185,129,0.30);">
          <div style="font-size:1.9rem;font-weight:800;color:#10b981;line-height:1;">
            {len(matrix['matched'])}
          </div>
          <div style="font-size:0.75rem;color:#a1a1aa;margin-top:4px;">Compétences matchées</div>
        </div>
        <div style="background:rgba(239,68,68,0.10);border-radius:14px;padding:14px;
                    border:1px solid rgba(239,68,68,0.30);">
          <div style="font-size:1.9rem;font-weight:800;color:#ef4444;line-height:1;">
            {len(matrix['missing'])}
          </div>
          <div style="font-size:0.75rem;color:#a1a1aa;margin-top:4px;">À combler</div>
        </div>
        <div style="background:rgba(139,92,246,0.10);border-radius:14px;padding:14px;
                    border:1px solid rgba(139,92,246,0.30);">
          <div style="font-size:1.9rem;font-weight:800;color:#8b5cf6;line-height:1;">
            {score}%
          </div>
          <div style="font-size:0.75rem;color:#a1a1aa;margin-top:4px;">
            Score Fit · {match_pct}% requis couverts
          </div>
        </div>
      </div>

      <div style="margin-bottom:14px;">
        <div style="font-size:0.72rem;color:#a1a1aa;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">✅ Maîtrisées</div>
        <div>{matched_html}</div>
      </div>

      <div style="margin-bottom:14px;">
        <div style="font-size:0.72rem;color:#a1a1aa;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">⚠️ À mentionner / Lacunes</div>
        <div>{missing_html}</div>
      </div>

      <div>
        <div style="font-size:0.72rem;color:#a1a1aa;text-transform:uppercase;
                    letter-spacing:.08em;margin-bottom:6px;">💡 Bonus (atouts non demandés)</div>
        <div>{bonus_html}</div>
      </div>
    </div>
    """


def render_radar_chart(matrix: dict) -> str:
    """Génère un radar chart en SVG pur."""
    # Simulation de scores basés sur la matrix
    total_job = matrix.get("total_job") or 1
    matched = len(matrix.get("matched", []))
    
    technical = min(100, round(matched / total_job * 100))
    domain = min(100, matrix.get("score", 0) + 10) # Bonus for matching
    soft = 85 # Default high for senior profile
    experience = 90 if matched > 3 else 60
    
    categories = [
        {"name": "Technique", "value": technical},
        {"name": "Domaine", "value": domain},
        {"name": "Soft Skills", "value": soft},
        {"name": "Expérience", "value": experience},
        {"name": "Global Match", "value": matrix.get("score", 0)}
    ]
    
    # SVG Params
    size = 300
    center = size / 2
    radius = (size / 2) - 40
    
    points = []
    labels = []
    grid_circles = [0.2, 0.4, 0.6, 0.8, 1.0]
    grid_html = ""
    
    import math
    
    for i, cat in enumerate(categories):
        angle = (i / len(categories)) * 2 * math.pi - math.pi / 2
        
        # Grid lines
        x_end = center + radius * math.cos(angle)
        y_end = center + radius * math.sin(angle)
        grid_html += f'<line x1="{center}" y1="{center}" x2="{x_end}" y2="{y_end}" stroke="rgba(255,255,255,0.1)" stroke-width="1" />'
        
        # Labels
        lx = center + (radius + 25) * math.cos(angle)
        ly = center + (radius + 15) * math.sin(angle)
        labels.append(f'<text x="{lx}" y="{ly}" text-anchor="middle" fill="#a1a1aa" font-size="10" font-weight="600">{cat["name"]}</text>')
        
        # Data points
        val_radius = (cat["value"] / 100) * radius
        px = center + val_radius * math.cos(angle)
        py = center + val_radius * math.sin(angle)
        points.append(f"{px},{py}")

    # Grid circles
    for gc in grid_circles:
        r = gc * radius
        grid_html += f'<circle cx="{center}" cy="{center}" r="{r}" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="1" />'

    polygon_points = " ".join(points)
    
    return f"""
    <div style="display:flex;justify-content:center;align-items:center;background:rgba(255,255,255,0.02);border-radius:16px;padding:10px;border:1px solid rgba(255,255,255,0.05);">
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        {grid_html}
        <polygon points="{polygon_points}" fill="rgba(139,92,246,0.3)" stroke="#8b5cf6" stroke-width="2" />
        {"".join(labels)}
        <circle cx="{center}" cy="{center}" r="3" fill="#8b5cf6" />
      </svg>
    </div>
    """


async def analyze_keyword_gap(job_description: str, profile: dict, llm=None) -> dict:
    """
    Analyse "instantanée" (avant génération) de l'adéquation profil/offre.
    Extrait les compétences de la JD via LLM et compare au profil.
    """
    if not job_description or not job_description.strip():
        return {"matched": [], "missing": []}

    profile_skills = _flatten_skills(profile)
    
    # 1. Extraction des skills de la JD
    job_skills_list = []
    if llm:
        from engine.prompts import build_skill_extraction_prompt
        prompt = build_skill_extraction_prompt(job_description)
        try:
            resp = await llm.generate(prompt)
            if resp:
                # Nettoyage et split
                job_skills_list = [s.strip().lower() for s in resp.split(",") if s.strip()]
        except Exception:
            pass

    # 2. Si l'extraction LLM a échoué ou est absente, fallback sur recherche par mots-clés du profil
    if not job_skills_list:
        jd_lower = job_description.lower()
        # On ne peut pas trouver de "missing" ici car on ne connaît pas les skills de la JD
        # On ne peut trouver que ce qui est "matched"
        matched = []
        for s in profile_skills:
            if s and s in jd_lower:
                matched.append(s)
        return {"matched": sorted(list(set(matched))), "missing": []}

    # 3. Comparaison intelligente
    matched = []
    missing = []
    
    for js in job_skills_list:
        # Fuzzy match simple : est-ce que le skill JD est dans le profil (ou vice versa)
        found = False
        for ps in profile_skills:
            if js in ps or ps in js:
                matched.append(js)
                found = True
                break
        if not found:
            missing.append(js)

    return {
        "matched": sorted(list(set(matched))),
        "missing": sorted(list(set(missing))),
    }
