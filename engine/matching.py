import json
from typing import Dict, List, Tuple, Any
from pathlib import Path

CONTENT_BUDGET = {
    "skills": {"target": 12, "minimum": 6},
}

TRANSVERSE_SKILL_MARKERS = {"python", "matlab", "simulink"}


def _skill_matches_keywords(skill_name: str, keywords: set[str]) -> bool:
    return any(kw in skill_name or skill_name in kw for kw in keywords if kw)


def _dedupe_skills(skills: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for skill in skills:
        name = skill.get("name", "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(skill)
    return out


def load_profile_index(json_path: str) -> dict:
    """Charge le JSON et le retourne sous forme de dictionnaire."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_safe_personal_info(raw_personal_info: dict) -> dict:
    """
    Parcours raw_personal_info. 
    Si une clé contient un dictionnaire avec "hidden": True ou "inject_in_prompt": False, 
    elle DOIT être exclue du dictionnaire retourné.
    """
    safe_info = {}
    for key, value in raw_personal_info.items():
        if isinstance(value, dict):
            if value.get("hidden") is True or value.get("inject_in_prompt") is False:
                continue
        safe_info[key] = value
    return safe_info

def extract_job_keywords(job_description: str, target_keywords_list: list[str]) -> list[str]:
    """
    Convertit la description en minuscules. 
    Retourne une liste des mots de target_keywords_list qui apparaissent dans la description.
    """
    desc_lower = job_description.lower()
    found_keywords = []
    for kw in target_keywords_list:
        if kw.lower() in desc_lower:
            found_keywords.append(kw)
    return found_keywords

def score_profiles(job_keywords: list[str], profile_index: dict) -> dict[str, float]:
    """
    Pour chaque profil dans profile_index["profiles"], 
    calcule un score basé sur le nombre de job_keywords matchant ses target_keywords.
    """
    scores = {}
    job_keywords_set = set(kw.lower() for kw in job_keywords)
    
    profiles = profile_index.get("profiles", {})
    for profile_id, profile_data in profiles.items():
        target_keywords = profile_data.get("target_keywords", [])
        match_count = 0
        for tkw in target_keywords:
            if tkw.lower() in job_keywords_set:
                match_count += 1
        
        # Simple score: count of matches
        scores[profile_id] = float(match_count)
        
    return scores

def select_best_profile(job_offer: dict, profile_index: dict) -> tuple[str, float]:
    """
    Extrait tous les target_keywords uniques de tous les profils. 
    Appelle extract_job_keywords puis score_profiles. 
    Retourne l'ID du meilleur profil et son score. 
    Si aucun match significatif, utiliser un fallback (ex: "simulation_rd").
    """
    all_target_keywords = set()
    profiles = profile_index.get("profiles", {})
    for p_data in profiles.values():
        all_target_keywords.update(p_data.get("target_keywords", []))
    
    job_description = job_offer.get("description", "") + " " + job_offer.get("title", "")
    job_keywords = extract_job_keywords(job_description, list(all_target_keywords))
    
    scores = score_profiles(job_keywords, profile_index)
    
    if not scores:
        return "simulation_rd", 0.0
    
    best_profile = max(scores, key=scores.get)
    best_score = scores[best_profile]
    
    if best_score == 0:
        return "simulation_rd", 0.0
        
    return best_profile, best_score

def filter_experiences_by_profile(profile_id: str, profile_index: dict, max_experiences: int = 5) -> list[dict]:
    """
    Filtre profile_index["experience_stark"] (ou la section contenant les expériences) 
    pour ne garder que celles où profile_id ou "all" est présent dans profiles_tags. 
    Limite à max_experiences.
    """
    # Note: Using "experience_stark" based on the new master_profile structure
    all_exps = profile_index.get("experience_stark", [])
    filtered = []
    
    # Priority experiences from profile definition
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})
    priority_ids = profile_def.get("priority_experiences", [])
    
    # First, pick priority experiences if they match tags (or just because they are priority)
    priority_exps = [e for e in all_exps if e.get("id") in priority_ids]
    filtered.extend(priority_exps)
    
    # Then add others that have the tag and aren't already included
    for exp in all_exps:
        if exp.get("id") in priority_ids:
            continue
        tags = exp.get("profiles_tags", [])
        if profile_id in tags or "all" in tags:
            filtered.append(exp)
            
    return filtered[:max_experiences]

def filter_skills_by_profile(profile_id: str, profile_index: dict, selected_experiences: list[dict] | None = None) -> dict:
    """Filtre les compétences en 3 couches pour éviter une section skills trop pauvre."""
    taxonomy = profile_index.get("skills_taxonomy", {})
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})
    target_keywords = set(kw.lower() for kw in profile_def.get("target_keywords", []))
    hard_skills = taxonomy.get("hard_skills", [])

    selected_experiences = selected_experiences or []
    contextual_keywords = set()
    for exp in selected_experiences:
        contextual_keywords.update(str(k).lower() for k in exp.get("K", []))

    layer_1 = []
    layer_2 = []
    layer_3 = []
    for skill in hard_skills:
        skill_name = str(skill.get("name", "")).lower()
        tags = {str(t).lower() for t in skill.get("profiles_tags", [])}

        if _skill_matches_keywords(skill_name, target_keywords):
            layer_1.append(skill)
        elif "all" in tags or any(marker in skill_name for marker in TRANSVERSE_SKILL_MARKERS):
            layer_2.append(skill)
        elif _skill_matches_keywords(skill_name, contextual_keywords):
            layer_3.append(skill)

    all_hard = _dedupe_skills(layer_1 + layer_2 + layer_3)
    selected = all_hard[:CONTENT_BUDGET["skills"]["target"]]
    if len(selected) < CONTENT_BUDGET["skills"]["minimum"]:
        selected_names = {s.get("name", "").strip().lower() for s in selected}
        remaining = [
            s for s in hard_skills if s.get("name", "").strip().lower() not in selected_names
        ]
        selected += remaining[: CONTENT_BUDGET["skills"]["minimum"] - len(selected)]

    filtered_skills = {
        "hard_skills": selected,
        "domain_knowledge": taxonomy.get("domain_knowledge", []),
        "soft_skills": taxonomy.get("soft_skills", []),
    }

    return filtered_skills
