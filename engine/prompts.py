import json
import re
from typing import Dict, List, Any
from .matching import get_safe_personal_info

# --- CONTRAINTES STRICTES ONE-PAGE ---
ONE_PAGE_CONSTRAINTS = """
[CONTRAINTES STRICTES — ONE PAGE — NON NÉGOCIABLES]

SUMMARY :
- MAXIMUM 3 lignes.
- MAXIMUM 400 caractères (espaces inclus).
- Format : 1 phrase de positionnement + 1 phrase de preuve chiffrée + 1 phrase de valeur ajoutée.
- INTERDIT : listes, tirets, sauts de ligne dans le summary.

EXPERIENCES — Pour CHAQUE expérience retenue :
- MAXIMUM 3 bullet points. Pas 4. Pas 5. Exactement 2 ou 3.
- MAXIMUM 120 caractères par bullet (espaces inclus).
- Format obligatoire : [Verbe d'action] + [Technologie/Méthode] + [Résultat chiffré].
- INTERDIT : phrases longues, sous-listes, contexte superflu.

HEADLINE :
- MAXIMUM 1 ligne.
- MAXIMUM 90 caractères.
- Format : [Domaine] | [Techno 1] · [Techno 2] · [Techno 3] | [Secteur/Valeur]

NOMBRE D'EXPÉRIENCES À INCLURE :
- MAXIMUM 3 expériences (les plus pertinentes pour l'offre).
- MINIMUM 2 expériences.
- Choisir parmi la liste fournie selon pertinence décroissante.

COMPÉTENCES :
- MAXIMUM 8 hard skills.
- Format : liste inline séparée par " · " (pas de tableau, pas de niveaux).
"""

def build_candidate_context(profile_id: str, profile_index: dict, filtered_experiences: list[dict], filtered_skills: dict) -> dict:
    """
    Assemble un dict combinant : 
    get_safe_personal_info(profile_index["personal_info"]), 
    le headline/summary du profil cible, 
    les expériences filtrées et les skills filtrés.
    """
    personal_info = get_safe_personal_info(profile_index.get("personal_info", {}))
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})
    
    context = {
        "personal_info": personal_info,
        "target_profile": {
            "id": profile_id,
            "headline": profile_def.get("headline", ""),
            "summary": profile_index.get("personal_info", {}).get("summary_default", "") # Fallback to default summary
        },
        "experiences": filtered_experiences,
        "skills": filtered_skills,
        "education": profile_index.get("education", [])
    }
    return context

def build_generation_prompt(job_offer: dict, candidate_context: dict, profile_id: str) -> dict:
    """
    Génère un dictionnaire structuré qui servira de prompt unique avec contraintes One-Page.
    """
    prompt_dict = {
        "role": "Expert en recrutement et chasseur de têtes spécialisé en ingénierie R&D.",
        "objective": f"Générer un CV et une lettre de motivation percutants pour le poste de {job_offer.get('title')} chez {job_offer.get('company')}.",
        "one_page_policy": ONE_PAGE_CONSTRAINTS,
        "constraints": [
            "INTERDICTION FORMELLE d'utiliser les mots : 'Apprenti', 'Étudiant', 'Élève'.",
            "Présenter le candidat comme un expert opérationnel immédiatement productif.",
            "Le ton doit être professionnel, technique et axé sur les résultats (impact-driven).",
            "Utiliser des verbes d'action forts.",
            "Toutes les sorties doivent être en Français."
        ],
        "input_data": {
            "job_offer": job_offer,
            "candidate_context": candidate_context
        },
        "output_format": {
            "cv": {
                "headline": {
                    "value": "string — MAX 90 chars",
                    "char_count": "integer"
                },
                "summary": {
                    "value": "string — MAX 400 chars, 3 lignes max",
                    "char_count": "integer"
                },
                "experiences": [
                    {
                        "id": "string — ID original",
                        "rewritten_title": "string — MAX 60 chars",
                        "bullets": [
                            "string — MAX 120 chars chacun, Verbe d'action + Résultat"
                        ]
                    }
                ],
                "skills_inline": "string — MAX 8 skills séparés par ' · '",
                "one_page_compliant": "boolean"
            },
            "cover_letter": "Texte de la lettre de motivation (3 paragraphes max)"
        }
    }
    return prompt_dict

def validate_llm_output_constraints(cv_data: dict) -> dict:
    """
    Valide et corrige les violations de contraintes One-Page avant compilation.
    """
    violations = []
    
    # Sécurité structurelle
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

    # 3. Nombre d'expériences
    exps = cv.get("experiences", [])
    if len(exps) > 3:
        exps = exps[:3]
        violations.append({"field": "experiences", "action": "cut_to_3"})
    
    # 4. Bullets par expérience
    for i, exp in enumerate(exps):
        bullets = exp.get("bullets", [])
        if len(bullets) > 3:
            bullets = bullets[:3]
            violations.append({"field": f"exp[{i}].bullets", "action": "cut_to_3"})
        
        for j, bullet in enumerate(bullets):
            if len(bullet) > 120:
                bullets[j] = _truncate_at_word(bullet, 120)
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "truncated"})
        exp["bullets"] = bullets
    
    cv["experiences"] = exps
    cv_data["cv"] = cv

    return {
        "cv_data": cv_data,
        "violations": violations,
        "had_violations": len(violations) > 0
    }

def _truncate_at_word(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    return truncated + "…"

def post_process_llm_output(raw_output: dict) -> dict:
    """
    Nettoie les mots interdits et valide les contraintes One-Page.
    """
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
