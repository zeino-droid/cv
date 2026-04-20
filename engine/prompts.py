import json
from typing import Dict, List, Any
from .matching import get_safe_personal_info

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
    Génère un dictionnaire structuré qui servira de prompt unique. 
    Il doit contenir des instructions strictes au LLM : 
    interdiction d'utiliser les mots "Apprenti", "Étudiant", "Élève". 
    Demander un format de sortie JSON avec les clés : 
    cv.headline, cv.summary, cv.experiences (avec titres et bullets réécrits), et cover_letter.
    """
    prompt_dict = {
        "role": "Expert en recrutement et chasseur de têtes spécialisé en ingénierie R&D.",
        "objective": f"Générer un CV et une lettre de motivation percutants pour le poste de {job_offer.get('title')} chez {job_offer.get('company')}.",
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
                "headline": "Titre professionnel adapté à l'offre",
                "summary": "Résumé professionnel de 3-4 lignes maximum",
                "experiences": [
                    {
                        "id": "ID de l'expérience",
                        "title": "Titre du poste réécrit pour l'offre",
                        "bullet_points": ["Point d'impact 1", "Point d'impact 2", "Point d'impact 3"]
                    }
                ]
            },
            "cover_letter": "Texte de la lettre de motivation (3 paragraphes max)"
        }
    }
    return prompt_dict

def post_process_llm_output(raw_output: dict) -> dict:
    """
    Scanne toutes les strings du dictionnaire généré par le LLM. 
    Si des mots interdits ("apprenti", "étudiant", "élève") sont trouvés, 
    nettoie-les ou lève un avertissement loggé.
    """
    forbidden_words = ["apprenti", "étudiant", "élève", "apprentissage", "etudiant", "eleve"]
    
    def clean_text(text: Any) -> Any:
        if isinstance(text, str):
            cleaned = text
            for word in forbidden_words:
                # Case insensitive replacement or removal
                import re
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                # Strategy: replace with "Ingénieur" or just remove depending on context. 
                # Here we'll just flag/remove for simplicity as per instructions.
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

    return clean_text(raw_output)
