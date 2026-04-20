import json
import re
from typing import Dict, List, Any
from .matching import get_safe_personal_info

# ============================================
# CONTRAINTES DE CONTENU (Phase 4)
# ============================================
PROJECT_CONSTRAINTS = """
[CONTRAINTES PROJETS — FORMAT COMPACT]
SECTION "PROJETS TECHNIQUES" (distincte de "EXPÉRIENCES") :
Pour CHAQUE projet retenu :
- TITRE : MAX 70 caractères — doit contenir le(s) outil(s) clé(s). Format : "[Sujet] — [Outil] | [Contexte]"
- DESCRIPTION : 1 seule ligne — MAX 150 caractères. Format : "[Verbe passé] + [méthode] + [résultat]"
- KEYWORDS : liste de 3 à 4 mots-clés techniques séparés par " · "
INTERDIT : Bullets multiples, mention "TP/cours" (utiliser "Projet").
"""

ONE_PAGE_CONSTRAINTS = """
[CONTRAINTES STRICTES — ONE PAGE — NON NÉGOCIABLES]

SUMMARY :
- MAXIMUM 3 lignes.
- MAXIMUM 400 caractères (espaces inclus).
- Format : 1 phrase de positionnement + 1 phrase de preuve chiffrée + 1 phrase de valeur ajoutée.
- INTERDIT : listes, tirets, sauts de ligne dans le summary.

EXPERIENCES (Pool A) :
- MAXIMUM 2 expériences.
- MAXIMUM 2 bullet points par expérience.
- MAXIMUM 120 caractères par bullet (espaces inclus).
- Format obligatoire : [Verbe d'action] + [Technologie/Méthode] + [Résultat chiffré].
- Style obligatoire : vocabulaire technique dense, précis, sans remplissage.

PROJETS (Pool B) :
""" + PROJECT_CONSTRAINTS + """

HEADLINE :
- MAXIMUM 1 ligne.
- MAXIMUM 90 caractères.
"""

def build_candidate_context(profile_id: str, profile_index: dict, filtered_experiences: list[dict], filtered_skills: dict) -> dict:
    """Prépare le contexte candidat pour le prompt."""
    personal_info = get_safe_personal_info(profile_index.get("personal_info", {}))
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})
    
    context = {
        "personal_info": personal_info,
        "target_profile": {
            "id": profile_id,
            "headline": profile_def.get("headline", ""),
            "summary": profile_index.get("personal_info", {}).get("summary_default", "")
        },
        "experiences": filtered_experiences,
        "skills": filtered_skills,
        "education": profile_index.get("education", [])
    }
    return context

def build_generation_prompt(job_offer: dict, candidate_context: dict, profile_id: str) -> dict:
    """Génère un dictionnaire structuré qui servira de prompt unique avec contraintes One-Page V2."""
    prompt_dict = {
        "role": "Expert en recrutement et chasseur de têtes spécialisé en ingénierie R&D.",
        "objective": f"Générer un CV percutant pour le poste de {job_offer.get('title')} chez {job_offer.get('company')}.",
        "one_page_policy": ONE_PAGE_CONSTRAINTS,
        "constraints": [
            "INTERDICTION FORMELLE d'utiliser les mots : 'Apprenti', 'Étudiant', 'Élève'.",
            "Présenter le candidat comme un expert opérationnel immédiatement productif.",
            "Le ton doit être professionnel, technique et axé sur les résultats.",
            "Utiliser un vocabulaire technique dense et précis pour maximiser l'information par ligne.",
            "Utiliser des verbes d'action forts.",
            "Toutes les sorties doivent être en Français."
        ],
        "input_data": {
            "job_offer": job_offer,
            "candidate_context": candidate_context
        },
        "output_format": {
            "cv": {
                "headline": {"value": "string — MAX 90 chars", "char_count": "integer"},
                "summary": {"value": "string — MAX 400 chars", "char_count": "integer"},
                "experiences": [
                    {
                        "id": "string",
                        "rewritten_title": "string — MAX 60 chars",
                        "bullets": ["string — MAX 120 chars (EXACTEMENT 2)"]
                    }
                ],
                "projects": [
                    {
                        "id": "string",
                        "rewritten_title": "string — MAX 70 chars",
                        "one_line_description": "string — MAX 150 chars",
                        "keywords_inline": "string — 3 à 4 mots techniques · séparés"
                    }
                ],
                "skills_inline": "string — MAX 15 skills séparés par ' · '",
                "one_page_compliant": "boolean"
            }
        }
    }
    return prompt_dict

def validate_llm_output_constraints(cv_data: dict) -> dict:
    """Valide et corrige les violations de contraintes One-Page V2."""
    violations = []
    if "cv" not in cv_data:
        return {"cv_data": cv_data, "violations": ["Missing 'cv' key"], "had_violations": True}

    cv = cv_data["cv"]

    # 1. Headline
    headline_obj = cv.get("headline", {})
    headline = headline_obj.get("value", "") if isinstance(headline_obj, dict) else str(headline_obj)
    if len(headline) > 90:
        headline = _truncate_at_word(headline, 90)
        violations.append({"field": "headline", "action": "truncated"})
    cv["headline"] = {"value": headline, "char_count": len(headline)}

    # 2. Summary
    summary_obj = cv.get("summary", {})
    summary = summary_obj.get("value", "") if isinstance(summary_obj, dict) else str(summary_obj)
    if len(summary) > 400:
        summary = _truncate_at_word(summary, 400)
        violations.append({"field": "summary", "action": "truncated"})
    cv["summary"] = {"value": summary, "char_count": len(summary)}

    # 3. Pool A : Expériences Pro (Max 2)
    exps = cv.get("experiences", [])
    if len(exps) > 2:
        exps = exps[:2]
        violations.append({"field": "experiences", "action": "cut_to_2"})
    
    for i, exp in enumerate(exps):
        bullets = exp.get("bullets", [])
        if len(bullets) > 2:
            bullets = bullets[:2]
            violations.append({"field": f"exp[{i}].bullets", "action": "cut_to_2"})
        for j, bullet in enumerate(bullets):
            if len(bullet) > 120:
                bullets[j] = _truncate_at_word(bullet, 120)
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "truncated"})
        exp["bullets"] = bullets
    cv["experiences"] = exps

    # 4. Pool B : Projets (Max 2)
    projs = cv.get("projects", [])
    if len(projs) > 2:
        projs = projs[:2]
        violations.append({"field": "projects", "action": "cut_to_2"})
    
    for i, proj in enumerate(projs):
        title = proj.get("rewritten_title", "")
        if len(title) > 70:
            proj["rewritten_title"] = _truncate_at_word(title, 70)
            violations.append({"field": f"proj[{i}].title", "action": "truncated"})
        
        desc = proj.get("one_line_description", "")
        if len(desc) > 150:
            proj["one_line_description"] = _truncate_at_word(desc, 150)
            violations.append({"field": f"proj[{i}].desc", "action": "truncated"})
    cv["projects"] = projs

    # 5. Skills inline (Max 15)
    skills_inline = cv.get("skills_inline", "")
    if isinstance(skills_inline, str) and skills_inline.strip():
        skills = [s.strip() for s in skills_inline.split("·") if s.strip()]
        if len(skills) > 15:
            skills = skills[:15]
            violations.append({"field": "skills_inline", "action": "cut_to_15"})
        cv["skills_inline"] = " · ".join(skills)

    cv_data["cv"] = cv
    return {"cv_data": cv_data, "violations": violations, "had_violations": len(violations) > 0}

def _truncate_at_word(text: str, max_chars: int) -> str:
    if len(text) <= max_chars: return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    return truncated + "…"

def post_process_llm_output(raw_output: dict) -> dict:
    """Nettoie les mots interdits et valide les contraintes."""
    forbidden_words = ["apprenti", "étudiant", "élève", "apprentissage", "etudiant", "eleve"]
    
    def clean_text(text: Any) -> Any:
        if isinstance(text, str):
            cleaned = text
            for word in forbidden_words:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                if word.lower() in ["apprenti", "étudiant", "élève"]:
                    cleaned = pattern.sub("Ingénieur", cleaned)
                else:
                    cleaned = pattern.sub("", cleaned)
            return cleaned
        elif isinstance(text, dict):
            return {k: clean_text(v) for k, v in text.items()}
        elif isinstance(text, list):
            return [clean_text(item) for item in text]
        return text

    cleaned_output = clean_text(raw_output)
    return validate_llm_output_constraints(cleaned_output)
