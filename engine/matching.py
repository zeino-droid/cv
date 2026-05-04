import json
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path

FILL_BUDGET = {
    "skills": 12,
    "skills_minimum": 6,
}
TRANSVERSAL_SKILL_MARKERS = {
    "python",
    "matlab",
    "simulink",
    "matlab / simulink",
    "git",
    "linux",
    "latex",
    "automatique",
    "commande",
}


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


def _force_include_transversal_skills(
    selected: list[dict], layer_1_names: set[str], transversal_skills: list[dict], budget: int
) -> list[dict]:
    """Garantit la présence des compétences transversales clés dans la sélection finale."""
    selected = list(selected)
    selected_names = {str(s.get("name", "")).strip().lower() for s in selected}
    transversal_names = {str(s.get("name", "")).strip().lower() for s in transversal_skills}

    for skill in transversal_skills:
        name = str(skill.get("name", "")).strip().lower()
        if not name or name in selected_names:
            continue

        if len(selected) < budget:
            selected.append(skill)
            selected_names.add(name)
            continue

        replace_idx = None
        for idx in range(len(selected) - 1, -1, -1):
            candidate_name = str(selected[idx].get("name", "")).strip().lower()
            if candidate_name not in transversal_names and candidate_name not in layer_1_names:
                replace_idx = idx
                break

        if replace_idx is None:
            for idx in range(len(selected) - 1, -1, -1):
                candidate_name = str(selected[idx].get("name", "")).strip().lower()
                if candidate_name not in transversal_names:
                    replace_idx = idx
                    break

        if replace_idx is not None:
            removed_name = str(selected[replace_idx].get("name", "")).strip().lower()
            selected[replace_idx] = skill
            selected_names.discard(removed_name)
            selected_names.add(name)

    return _dedupe_skills(selected)[:budget]


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

def filter_skills_by_profile(profile_id: str, profile_index: dict, selected_experiences: Optional[List[Dict]] = None) -> dict:
    """Sélection des hard skills en 3 couches et applique un floor de remplissage.

    Layer 1: compétences signature liées aux mots-clés du profil.
    Layer 2: compétences transversales via whitelist.
    Layer 3: reste trié par niveau (et léger boost contextuel si expérience fournie).
    """
    taxonomy = profile_index.get("skills_taxonomy", {})
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})
    hard_skills = taxonomy.get("hard_skills", [])
    target_kw_low = {kw.lower() for kw in profile_def.get("target_keywords", [])}

    selected_experiences = selected_experiences or []
    contextual_keywords = {
        str(k).lower()
        for exp in selected_experiences
        for k in exp.get("K", [])
    }

    layer_1 = [
        s
        for s in hard_skills
        if any(
            str(s.get("name", "")).lower() in kw or kw in str(s.get("name", "")).lower()
            for kw in target_kw_low
        )
    ]

    l1_names = {str(s.get("name", "")).lower() for s in layer_1}
    layer_2 = [
        s
        for s in hard_skills
        if str(s.get("name", "")).lower() in TRANSVERSAL_SKILL_MARKERS
        and str(s.get("name", "")).lower() not in l1_names
    ]

    skill_level_weights = {"avancé": 3, "intermédiaire": 2, "débutant": 1}
    selected_names = l1_names | {str(s.get("name", "")).lower() for s in layer_2}
    layer_3_pool = [
        s
        for s in hard_skills
        if str(s.get("name", "")).lower() not in selected_names
    ]

    def _layer3_sort_key(skill: dict) -> tuple[int, int]:
        skill_name_low = str(skill.get("name", "")).lower()
        level_weight = skill_level_weights.get(str(skill.get("level", "")).lower(), 0)
        contextual_match = int(
            any(kw in skill_name_low or skill_name_low in kw for kw in contextual_keywords)
        )
        return level_weight, contextual_match

    layer_3_pool.sort(
        key=_layer3_sort_key,
        reverse=True,
    )

    base_selection = _dedupe_skills(layer_1 + layer_3_pool)[: FILL_BUDGET["skills"]]
    selected = _force_include_transversal_skills(
        base_selection,
        layer_1_names=l1_names,
        transversal_skills=layer_2,
        budget=FILL_BUDGET["skills"],
    )

    # --- SKILL FLOOR LOGIC ---
    # Ensure every hard skill listed is backed by at least one "Action Bullet" (keyword) in selected experiences.
    # This creates an "Evidence-Based CV".
    
    proven_skills = []
    skill_proofs = {} # Map skill_name -> experience_id or "academic"
    
    for skill in selected:
        skill_name_low = str(skill.get("name", "")).lower()
        proof_found = False
        
        # Check in selected experiences
        for exp in selected_experiences:
            exp_keywords = {str(k).lower() for k in exp.get("K", [])}
            if any(skill_name_low in kw or kw in skill_name_low for kw in exp_keywords):
                proven_skills.append(skill)
                skill_proofs[skill.get("name")] = {
                    "type": "experience",
                    "id": exp.get("id"),
                    "title": exp.get("title"),
                    "company": exp.get("company")
                }
                proof_found = True
                break
        
        if not proof_found:
            # Fallback check in academic foundations or context field
            if skill.get("context"):
                proven_skills.append(skill)
                skill_proofs[skill.get("name")] = {
                    "type": "context",
                    "text": skill.get("context")
                }
            else:
                # If truly unproven, we exclude it from the final list to respect the "Skill Floor"
                pass

    # Re-limit to budget after filtering
    final_hard_skills = proven_skills[: FILL_BUDGET["skills"]]

    filtered_skills = {
        "hard_skills": final_hard_skills,
        "skill_proofs": skill_proofs,
        "domain_knowledge": taxonomy.get("domain_knowledge", []),
        "soft_skills": taxonomy.get("soft_skills", []),
        "fill_layers": {
            "layer_1_signature": len(layer_1),
            "layer_2_transversal": len(layer_2),
            "skills_total": len(final_hard_skills),
        },
    }

    return filtered_skills
