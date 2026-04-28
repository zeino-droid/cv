import re
from collections import Counter
from typing import Any, Dict, List, Optional, TypedDict
from .matching import get_safe_personal_info


class CandidateContext(TypedDict, total=False):
    """Structure attendue du contexte candidat."""
    personal_info: Dict[str, Any]
    target_profile: Dict[str, str]
    experiences: List[Dict[str, Any]]
    skills: Dict[str, Any]
    education: List[Dict[str, Any]]
    ranked_projects: List[Dict[str, Any]]
    detected_action_verbs: List[str]
    profile_priority_ids: List[str]


# ============================================
# SOURCE UNIQUE DES CONTRAINTES (Phase 4)
# ============================================
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
    "headline_max_chars": 90,
    "project_title_max_chars": 70,
    "project_desc_min_chars": 60,
    "project_desc_max_chars": 150,
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
- Rédiger des puces naturelles, concrètes et orientées impact

PROJETS:
- MIN {config["min_projects"]}, MAX {config["max_projects"]} projets
- Titre MAX {config["project_title_max_chars"]} chars
- Description MIN {config["project_desc_min_chars"]} chars, MAX {config["project_desc_max_chars"]} chars
- Keywords: 3 à 4 mots techniques séparés par " · "

SKILLS:
- MIN {config["skills_min"]}, MAX {config["skills_count"]} hard skills
- INTERDIT d'en mettre moins que le minimum

HEADLINE:
- MAX {config["headline_max_chars"]} chars
- Format recommandé : [Métier ciblé] | [2-3 expertises techniques clés]
- Éviter les formulations génériques ("Ingénieur", "Profil polyvalent", etc.)
"""


def _extract_action_verbs(action_field: Any) -> List[str]:
    """Extrait les verbes d'action du champ A (STAR) d'une expérience.

    Le champ peut être une liste de puces ou un bloc de texte.
    On prend le premier mot de chaque puce/phrase comme verbe candidat.
    """
    if not action_field:
        return []
    if isinstance(action_field, list):
        sentences = action_field
    else:
        sentences = re.split(r"(?<=[.!?])\s+|[\n;]", str(action_field))
    verbs: List[str] = []
    for s in sentences:
        m = re.match(r"^([A-ZÀ-Ÿa-zà-ÿ]{3,})", s.strip())
        if m:
            verbs.append(m.group(1))
    return verbs


def build_candidate_context(profile_id: str, profile_index: Dict, filtered_experiences: List[Dict], filtered_skills: Dict) -> CandidateContext:
    """Prépare le contexte candidat pour le prompt.

    Enrichit chaque expérience avec les champs STAR dérivés (action_verbs,
    concrete_results, business_context) quand ils sont disponibles, sans
    modifier les champs d'origine.
    """
    personal_info = get_safe_personal_info(profile_index.get("personal_info", {}))
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})

    # Enrichissement STAR par expérience (uniquement quand les champs existent)
    enriched_experiences: List[Dict] = []
    all_action_verbs: List[str] = []
    for exp in filtered_experiences:
        enriched = dict(exp)
        action_verbs = _extract_action_verbs(exp.get("A"))
        if action_verbs:
            enriched["action_verbs"] = action_verbs
            all_action_verbs.extend(action_verbs)
        if exp.get("R"):
            enriched["concrete_results"] = exp["R"]
        business_ctx = exp.get("S") or exp.get("T")
        if business_ctx:
            enriched["business_context"] = business_ctx
        enriched_experiences.append(enriched)

    context = {
        "personal_info": personal_info,
        "target_profile": {
            "id": profile_id,
            "headline": profile_def.get("headline", ""),
            "summary": profile_index.get("personal_info", {}).get("summary_default", "")
        },
        "experiences": enriched_experiences,
        "skills": filtered_skills,
        "education": profile_index.get("education", []),
        "profile_priority_ids": profile_def.get("priority_experiences", []),
        "detected_action_verbs": sorted(set(all_action_verbs)),
    }
    return context

def build_generation_prompt(job_offer: Dict, candidate_context: CandidateContext, profile_id: str, content_config: Optional[Dict] = None) -> Dict:
    """Génère un dictionnaire structuré qui servira de prompt unique avec contraintes One-Page V2.

    Les contraintes de format (longueurs, comptages) sont centralisées dans
    ``one_page_policy`` via :func:`build_one_page_constraints`.
    Les ``constraints`` ici ne portent que sur la sémantique et la qualité du contenu.
    """
    content_cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    prompt_dict = {
        "role": "Expert en recrutement et chasseur de têtes spécialisé en ingénierie R&D.",
        "objective": f"Générer un CV percutant pour le poste de {job_offer.get('title')} chez {job_offer.get('company')}.",
        "one_page_policy": build_one_page_constraints(content_cfg),
        "constraints": [
            # ── HONNÊTETÉ ABSOLUE ──────────────────────────────────────────
            "INTERDIT : N'invente, n'ajoute, ni ne suppose aucune compétence, outil, diplôme ou expérience absent de candidate_context.",
            "Si une compétence de l'offre est absente du profil : ne la mentionne pas. Jamais.",
            "Travaille exclusivement avec ce qui est fourni dans input_data.candidate_context.",
            # ── ADAPTATION INTELLIGENTE (pas du copier-coller) ─────────────
            "Pour chaque expérience ou projet, identifie l'angle le plus pertinent pour l'offre et reformule dans ce sens.",
            "Utilise les mots-clés EXACTS de l'offre dès qu'une expérience du profil le justifie réellement.",
            "Trie les expériences et projets par pertinence pour l'offre — pas forcément par ordre chronologique.",
            "Si l'expérience pro est courte, mets en avant les projets académiques directement liés à l'offre.",
            # ── CONTENU DES BULLETS ────────────────────────────────────────
            "Chaque bullet : verbe d'action fort + outil/méthode concret + résultat ou contexte mesurable si disponible.",
            "Exploite les champs 'concrete_results', 'action_verbs' et 'business_context' injectés dans candidate_context si présents.",
            "INTERDICTION FORMELLE d'utiliser les mots : 'Apprenti', 'Étudiant', 'Élève'.",
            "Présenter le candidat comme un expert opérationnel immédiatement productif.",
            # ── RÉSUMÉ ─────────────────────────────────────────────────────
            "Le résumé : structure = profil général → compétences clés matchées avec l'offre → valeur ajoutée concrète.",
            "Le résumé doit reprendre les mots-clés de l'offre présents dans le profil, jamais des termes inventés.",
            # ── STYLE ──────────────────────────────────────────────────────
            "Le ton doit être professionnel, technique et axé sur les résultats.",
            "La headline doit être ultra-ciblée au poste visé et inclure des expertises techniques concrètes.",
            "Toutes les sorties doivent être en Français."
        ],
        "input_data": {
            "job_offer": job_offer,
            "candidate_context": candidate_context
        },
        "output_format": {
            "cv": {
                "headline": {"value": "string", "char_count": "integer"},
                "summary": {"value": "string", "char_count": "integer"},
                "experiences": [
                    {
                        "id": "string",
                        "rewritten_title": "string",
                        "bullets": ["string"]
                    }
                ],
                "projects": [
                    {
                        "id": "string",
                        "rewritten_title": "string",
                        "one_line_description": "string",
                        "keywords_inline": "string — mots techniques · séparés"
                    }
                ],
                "skills_inline": "string — skills séparés par ' · '",
                "one_page_compliant": "boolean"
            }
        }
    }
    return prompt_dict

def validate_llm_output_constraints(cv_data: Dict, content_config: Optional[Dict] = None) -> Dict:
    """Valide et corrige les violations de contraintes One-Page V2.

    Pour chaque champ dépassant les limites, la valeur est tronquée en mode
    sécurisé (fallback) et le champ original est ajouté dans ``fields_to_rewrite``
    afin que l'appelant puisse optionnellement déclencher une réécriture contrôlée
    via :func:`build_compression_prompt` plutôt que de conserver la troncature brute.
    """
    cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    violations = []
    fields_to_rewrite: List[Dict] = []
    if "cv" not in cv_data:
        return {"cv_data": cv_data, "violations": ["Missing 'cv' key"], "had_violations": True, "fields_to_rewrite": []}

    cv = cv_data["cv"]

    # 1. Headline
    headline_obj = cv.get("headline", {})
    headline = headline_obj.get("value", "") if isinstance(headline_obj, dict) else str(headline_obj)
    if len(headline) > cfg["headline_max_chars"]:
        fields_to_rewrite.append({"field": "headline", "original": headline, "max_chars": cfg["headline_max_chars"]})
        headline = _truncate_at_word(headline, cfg["headline_max_chars"])
        violations.append({"field": "headline", "action": "truncated"})
    cv["headline"] = {"value": headline, "char_count": len(headline)}

    # 2. Summary
    summary_obj = cv.get("summary", {})
    summary = summary_obj.get("value", "") if isinstance(summary_obj, dict) else str(summary_obj)
    if len(summary) > cfg["summary_max_chars"]:
        fields_to_rewrite.append({"field": "summary", "original": summary, "max_chars": cfg["summary_max_chars"], "min_chars": cfg["summary_min_chars"]})
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
                fields_to_rewrite.append({"field": f"exp[{i}].bullet[{j}]", "original": bullet, "max_chars": cfg["max_bullet_chars"], "min_chars": cfg["min_bullet_chars"]})
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
        if len(title) > cfg["project_title_max_chars"]:
            proj["rewritten_title"] = _truncate_at_word(title, cfg["project_title_max_chars"])
            violations.append({"field": f"proj[{i}].title", "action": "truncated"})

        desc = proj.get("one_line_description", "")
        if len(desc) > cfg["project_desc_max_chars"]:
            fields_to_rewrite.append({"field": f"proj[{i}].desc", "original": desc, "max_chars": cfg["project_desc_max_chars"], "min_chars": cfg["project_desc_min_chars"]})
            proj["one_line_description"] = _truncate_at_word(desc, cfg["project_desc_max_chars"])
            violations.append({"field": f"proj[{i}].desc", "action": "truncated"})
    cv["projects"] = projs

    # 5. Skills inline (Min/Max) — accepts · or • as separators, normalises to ·
    skills_inline = cv.get("skills_inline", "")
    if isinstance(skills_inline, str) and skills_inline.strip():
        skills = [s.strip() for s in re.split(r"\s*[·•]\s*", skills_inline) if s.strip()]
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
    return {"cv_data": cv_data, "violations": violations, "had_violations": len(violations) > 0, "fields_to_rewrite": fields_to_rewrite}

def _truncate_at_word(text: str, max_chars: int) -> str:
    if len(text) <= max_chars: return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    return truncated + "…"

def post_process_llm_output(raw_output: Dict, content_config: Optional[Dict] = None) -> Dict:
    """Valide les contraintes sans remplacement automatique de mots."""
    return validate_llm_output_constraints(raw_output, content_config=content_config)


def build_compression_prompt(field_name: str, original_text: str, max_chars: int, min_chars: int = 0) -> Dict:
    """Construit un prompt pour demander au LLM de réécrire un champ trop long.

    À utiliser à la place d'une troncature brute quand ``validate_llm_output_constraints``
    signale un champ dans ``fields_to_rewrite``.  Le prompt retourné peut être
    passé directement à n'importe quel engine LLM ; le modèle doit répondre avec
    uniquement le texte réécrit (pas de JSON, pas de préambule).

    Args:
        field_name: Nom lisible du champ (ex. ``"summary"``, ``"exp[0].bullet[1]"``).
        original_text: Valeur originale produite par le LLM, avant troncature.
        max_chars: Limite supérieure de longueur à respecter.
        min_chars: Limite inférieure de longueur (0 = pas de minimum).

    Returns:
        Dictionnaire de prompt structuré compatible avec les engines du projet.
    """
    length_constraint = f"MAX {max_chars} caractères"
    if min_chars > 0:
        length_constraint = f"MIN {min_chars} / MAX {max_chars} caractères"
    return {
        "role": "Expert en rédaction professionnelle de CV pour ingénieurs en France.",
        "task": (
            f"Réécrire le champ « {field_name} » du CV pour qu'il respecte "
            f"la contrainte de longueur ({length_constraint}) "
            f"sans perdre les informations clés ni tronquer brutalement les phrases."
        ),
        "constraints": [
            f"Longueur cible : {length_constraint}.",
            "Conserver le sens, les mots-clés techniques et les chiffres présents.",
            "Réécrire de manière fluide et naturelle — ne pas couper au milieu d'une idée.",
            "Répondre UNIQUEMENT avec le texte réécrit, sans commentaires ni balises JSON.",
            "Langue : Français.",
        ],
        "original_text": original_text,
        "field_name": field_name,
        "max_chars": max_chars,
        "min_chars": min_chars,
    }


def assess_output_quality(cv_data: Dict) -> Dict:
    """Évalue la qualité éditoriale perçue d'un CV généré par le LLM.

    Les métriques calculées sont :

    - **lexical_diversity** : rapport mots uniques / total dans les bullets et le résumé.
      Proche de 1 = peu de répétitions lexicales, proche de 0 = vocabulaire pauvre.
    - **has_results_markers** : présence d'au moins un indicateur de résultat concret
      (chiffres, pourcentages, mots tels que « réduction », « gain », « optimisation »).
    - **repetition_rate** : fraction des bullets qui commencent par le même verbe
      d'action.  0 = aucune répétition, 1 = tous les bullets ont le même premier mot.
    - **quality_score** : score global sur 100 combinant les trois métriques ci-dessus.

    Args:
        cv_data: Dictionnaire CV tel que retourné par ``post_process_llm_output`` (clé
            ``"cv"`` au niveau racine) ou directement le sous-dict ``"cv"`` assemblé
            par ``_assemble_final_data``.

    Returns:
        Dictionnaire ``{lexical_diversity, has_results_markers, repetition_rate,
        quality_score, total_words, unique_words}``.
    """
    # Accepte cv_data["cv"] ou directement le dict cv assemblé
    cv = cv_data.get("cv", cv_data)

    all_texts: List[str] = []

    # Bullets des expériences
    for exp in cv.get("experiences", []):
        bullets = exp.get("bullets") or exp.get("achievements") or []
        all_texts.extend(str(b) for b in bullets if b)

    # Résumé
    summary = cv.get("summary", {})
    if isinstance(summary, dict):
        summary = summary.get("value", "")
    if summary:
        all_texts.append(str(summary))

    # 1. Diversité lexicale (sur l'ensemble des textes)
    words: List[str] = []
    for text in all_texts:
        words.extend(re.findall(r"\b[a-zA-ZÀ-ÿ]{3,}\b", text.lower()))
    total_words = len(words)
    unique_words = len(set(words))
    lexical_diversity = unique_words / total_words if total_words > 0 else 0.0

    # 2. Marqueurs de résultats (chiffres, %, indicateurs qualitatifs fréquents)
    results_pattern = re.compile(
        r"\d+\s*[%\+xX]?"
        r"|\bréduction\b|\bamélioration\b|\boptimisation\b|\bgain\b"
        r"|\baugmentation\b|\baccélération\b|\béconomie\b|\bperformance\b",
        re.IGNORECASE,
    )
    has_results_markers = any(results_pattern.search(t) for t in all_texts)

    # 3. Taux de répétition (premier mot des bullets uniquement)
    bullet_starts: List[str] = []
    for exp in cv.get("experiences", []):
        for b in (exp.get("bullets") or exp.get("achievements") or []):
            m = re.match(r"^([A-ZÀ-Ÿa-zà-ÿ]{3,})", str(b).strip())
            if m:
                bullet_starts.append(m.group(1).lower())
    repetition_rate = 0.0
    if len(bullet_starts) > 1:
        most_common_count = Counter(bullet_starts).most_common(1)[0][1]
        repetition_rate = most_common_count / len(bullet_starts)

    # 4. Score global (100 pts)
    score = 0
    score += min(40, int(lexical_diversity * 40))          # max 40 pts — diversité
    score += 30 if has_results_markers else 0              # 30 pts — résultats concrets
    score += max(0, 30 - int(repetition_rate * 60))        # max 30 pts — pénalité répétitions

    return {
        "lexical_diversity": round(lexical_diversity, 3),
        "has_results_markers": has_results_markers,
        "repetition_rate": round(repetition_rate, 3),
        "quality_score": score,
        "total_words": total_words,
        "unique_words": unique_words,
    }
