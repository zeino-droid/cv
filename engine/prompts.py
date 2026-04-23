import json
import re
from typing import Dict, List, Any, Optional
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

DEFAULT_CONTENT_CONFIG = {
    "summary_min_chars": 280,
    "summary_max_chars": 420,
    "max_pro_exp": 4,
    "min_pro_exp": 2,
    "max_projects": 2,
    "min_projects": 1,
    "max_bullets": 2,
    "min_bullet_chars": 35,
    "max_bullet_chars": 120,
    "skills_count": 12,
    "skills_min": 6,
}


def build_one_page_constraints(content_config: Optional[Dict] = None) -> str:
    config = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    return f"""
[CONTRAINTES STRICTES — ONE PAGE — NON NÉGOCIABLES]

SUMMARY:
- MIN {config["summary_min_chars"]} chars, MAX {config["summary_max_chars"]} chars
- EXACTEMENT 3 phrases

EXPERIENCES:
- MIN {config["min_pro_exp"]}, MAX {config["max_pro_exp"]} expériences
- EXACTEMENT {config["max_bullets"]} bullets par expérience
- MIN {config["min_bullet_chars"]}, MAX {config["max_bullet_chars"]} chars par bullet
- Obligatoire : [Verbe] + [Outil] + [Résultat chiffré]

PROJETS:
- MIN {config["min_projects"]}, MAX {config["max_projects"]} projets
- Titre MAX 70 chars
- Description MIN 60 chars, MAX 150 chars
- Keywords: 3 à 4 mots techniques séparés par " · "

SKILLS:
- MIN {config["skills_min"]}, MAX {config["skills_count"]} hard skills
- INTERDIT d'en mettre moins que le minimum

HEADLINE:
- MAX 90 chars
- Format recommandé : [Métier ciblé] | [2-3 expertises techniques clés]
- Éviter les formulations génériques ("Ingénieur", "Profil polyvalent", etc.)
"""


def build_candidate_context(profile_id: str, profile_index: Dict, filtered_experiences: List[Dict], filtered_skills: Dict) -> Dict:
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

def build_generation_prompt(job_offer: Dict, candidate_context: Dict, profile_id: str, content_config: Optional[Dict] = None) -> Dict:
    """Génère un dictionnaire structuré qui servira de prompt unique avec contraintes One-Page V2."""
    content_cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    prompt_dict = {
        "role": "Expert en recrutement et chasseur de têtes spécialisé en ingénierie R&D.",
        "objective": f"Générer un CV percutant pour le poste de {job_offer.get('title')} chez {job_offer.get('company')}.",
        "one_page_policy": build_one_page_constraints(content_cfg),
        "constraints": [
            "INTERDICTION FORMELLE d'utiliser les mots : 'Apprenti', 'Étudiant', 'Élève'.",
            "Présenter le candidat comme un expert opérationnel immédiatement productif.",
            "Le ton doit être professionnel, technique et axé sur les résultats.",
            "Utiliser un vocabulaire technique dense et précis pour maximiser l'information par ligne.",
            "Utiliser des verbes d'action forts.",
            "La headline doit être ultra-ciblée au poste visé et inclure des expertises techniques concrètes.",
            "Toutes les sorties doivent être en Français."
        ],
        "input_data": {
            "job_offer": job_offer,
            "candidate_context": candidate_context
        },
        "output_format": {
            "cv": {
                "headline": {"value": "string — MAX 90 chars", "char_count": "integer"},
                "summary": {"value": f"string — MIN {content_cfg['summary_min_chars']} / MAX {content_cfg['summary_max_chars']} chars", "char_count": "integer"},
                "experiences": [
                    {
                        "id": "string",
                        "rewritten_title": "string — MAX 60 chars",
                        "bullets": [f"string — MIN {content_cfg['min_bullet_chars']} / MAX {content_cfg['max_bullet_chars']} chars (EXACTEMENT {content_cfg['max_bullets']})"]
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
                "skills_inline": f"string — MIN {content_cfg['skills_min']} / MAX {content_cfg['skills_count']} skills séparés par ' · '",
                "one_page_compliant": "boolean"
            }
        }
    }
    return prompt_dict

def validate_llm_output_constraints(cv_data: Dict, content_config: Optional[Dict] = None) -> Dict:
    """Valide et corrige les violations de contraintes One-Page V2."""
    cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
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
    if len(summary) > cfg["summary_max_chars"]:
        summary = _truncate_at_word(summary, cfg["summary_max_chars"])
        violations.append({"field": "summary", "action": "truncated"})
    elif summary and len(summary) < cfg["summary_min_chars"]:
        violations.append({"field": "summary", "action": "below_min"})
    cv["summary"] = {"value": summary, "char_count": len(summary)}

    # 3. Pool A : Expériences Pro (Min/Max)
    exps = cv.get("experiences", [])
    if len(exps) > cfg["max_pro_exp"]:
        exps = exps[: cfg["max_pro_exp"]]
        violations.append({"field": "experiences", "action": "cut_to_max"})
    if exps and len(exps) < cfg["min_pro_exp"]:
        violations.append({"field": "experiences", "action": "below_min"})
    
    for i, exp in enumerate(exps):
        bullets = exp.get("bullets", [])
        if len(bullets) > cfg["max_bullets"]:
            bullets = bullets[: cfg["max_bullets"]]
            violations.append({"field": f"exp[{i}].bullets", "action": "cut_to_max"})
        for j, bullet in enumerate(bullets):
            if len(bullet) > cfg["max_bullet_chars"]:
                bullets[j] = _truncate_at_word(bullet, cfg["max_bullet_chars"])
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "truncated"})
            elif bullet and len(bullet) < cfg["min_bullet_chars"]:
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "below_min"})
        exp["bullets"] = bullets
    cv["experiences"] = exps

    # 4. Pool B : Projets (Min/Max)
    projs = cv.get("projects", [])
    if len(projs) > cfg["max_projects"]:
        projs = projs[: cfg["max_projects"]]
        violations.append({"field": "projects", "action": "cut_to_max"})
    if projs and len(projs) < cfg["min_projects"]:
        violations.append({"field": "projects", "action": "below_min"})
    
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

    # 5. Skills inline (Min/Max)
    skills_inline = cv.get("skills_inline", "")
    if isinstance(skills_inline, str) and skills_inline.strip():
        skills = [s.strip() for s in skills_inline.split("·") if s.strip()]
        if len(skills) > cfg["skills_count"]:
            skills = skills[: cfg["skills_count"]]
            violations.append({"field": "skills_inline", "action": "cut_to_max"})
        if len(skills) < cfg["skills_min"]:
            violations.append({"field": "skills_inline", "action": "below_min"})
            missing = cfg["skills_min"] - len(skills)
            for i in range(missing):
                skills.append(f"Compétence additionnelle {i + 1}")
        cv["skills_inline"] = " · ".join(skills)

    cv_data["cv"] = cv
    return {"cv_data": cv_data, "violations": violations, "had_violations": len(violations) > 0}

def _truncate_at_word(text: str, max_chars: int) -> str:
    if len(text) <= max_chars: return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    return truncated + "…"

def post_process_llm_output(raw_output: Dict, content_config: Optional[Dict] = None) -> Dict:
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
    return validate_llm_output_constraints(cleaned_output, content_config=content_config)
