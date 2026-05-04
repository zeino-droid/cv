import re
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
    domain_knowledge: List[str]
    matched_job_keywords: List[str]


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

# Tolérance souple : le post-traitement ne tronque qu'au-delà de ce ratio
SOFT_TOLERANCE_RATIO = 1.15


def build_one_page_constraints(content_config: Optional[Dict] = None) -> str:
    """Génère les gardes-fous de format, présentés comme des GUIDELINES plutôt que des interdictions."""
    config = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    return f"""
[GUIDELINES DE FORMAT — ONE PAGE]

Vise ces cibles. Un léger dépassement (~10%) est toléré si le contenu le justifie.

RÉSUMÉ : ~{config["summary_min_chars"]}-{config["summary_max_chars"]} caractères, 3 phrases.
EXPÉRIENCES : {config["min_pro_exp"]} à {config["max_pro_exp"]} expériences, {config["max_bullets"]} puces par expérience (~{config["min_bullet_chars"]}-{config["max_bullet_chars"]} chars/puce).
PROJETS : {config["min_projects"]} à {config["max_projects"]} projets, titre ~{config["project_title_max_chars"]} chars, description ~{config["project_desc_min_chars"]}-{config["project_desc_max_chars"]} chars, 3-4 mots-clés techniques séparés par " · ".
SKILLS : {config["skills_min"]} à {config["skills_count"]} hard skills séparés par " · ".
HEADLINE : ~{config["headline_max_chars"]} chars. Formulation ciblée au poste, pas générique.
"""


def build_candidate_context(profile_id: str, profile_index: Dict, filtered_experiences: List[Dict], filtered_skills: Dict) -> CandidateContext:
    """Prépare le contexte candidat enrichi pour le prompt.

    Action 3 — Ajoute target_keywords et domain_knowledge pour que le LLM
    sache exactement quels mots-clés cibler et quels domaines mettre en avant.
    """
    personal_info = get_safe_personal_info(profile_index.get("personal_info", {}))
    profile_def = profile_index.get("profiles", {}).get(profile_id, {})

    context = {
        "personal_info": personal_info,
        "target_profile": {
            "id": profile_id,
            "headline": profile_def.get("headline", ""),
            "summary": profile_index.get("personal_info", {}).get("summary_default", ""),
            "target_keywords": profile_def.get("target_keywords", []),
        },
        "experiences": filtered_experiences,
        "skills": filtered_skills,
        "education": profile_index.get("education", []),
        "domain_knowledge": filtered_skills.get("domain_knowledge", []),
    }
    return context


PERSONA_CONFIG = {
    "Research": {
        "mission_prefix": "Tu es un Chercheur Senior en R&D.",
        "tone": "scientifique, rigoureux, axé sur l'innovation et la méthodologie.",
        "focus": "Mets l'accent sur la démarche scientifique, les publications (si présentes), les brevets et la résolution de problèmes complexes.",
    },
    "Industrial": {
        "mission_prefix": "Tu es un Ingénieur d'Affaires / Responsable de Production Senior.",
        "tone": "pragmatique, axé sur l'efficacité, les normes et la livraison.",
        "focus": "Mets l'accent sur les process industriels, la conformité, la sécurité, l'optimisation des coûts et les résultats opérationnels concrets.",
    },
    "Startup": {
        "mission_prefix": "Tu es un CTO / Head of Engineering en startup à forte croissance.",
        "tone": "dynamique, polyvalent, axé sur la vitesse et l'impact.",
        "focus": "Mets l'accent sur l'agilité, la capacité à construire de zéro (0 to 1), la scalabilité et l'impact direct sur le produit.",
    },
}


def build_generation_prompt(job_offer: Dict, candidate_context: CandidateContext, profile_id: str, content_config: Optional[Dict] = None, persona: str = "Industrial", seniority_level: float = 0.5) -> Dict:
    """Génère un prompt structuré : mission narrative → brief éditorial → gardes-fous.

    Action 1 — Le LLM reçoit d'abord la mission (quoi + pourquoi), puis les
    consignes d'écriture (comment), et enfin les limites de format (combien).
    Action 4 — Le output_format est épuré : plus de char_count ni d'annotations
    redondantes avec les guidelines.
    """
    content_cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    
    # Configuration du persona
    p_cfg = PERSONA_CONFIG.get(persona, PERSONA_CONFIG["Industrial"])

    # Extraction du nom candidat pour personnaliser la mission
    candidate_name = candidate_context.get("personal_info", {}).get("name", "le candidat")
    job_title = job_offer.get("title", "Ingénieur")
    company = job_offer.get("company", "l'entreprise")

    # Mots-clés matchés (intersection profil × offre) pour guider le LLM
    matched_kw = candidate_context.get("matched_job_keywords", [])
    matched_kw_str = ", ".join(matched_kw[:10]) if matched_kw else "(non calculés)"

    # Domaines métier pour enrichir le récit
    domain_knowledge = candidate_context.get("domain_knowledge", [])
    domain_str = ", ".join(domain_knowledge[:6]) if domain_knowledge else ""

    prompt_dict = {
        # ═══════════════════════════════════════════════════════════
        # BLOC 1 — LA MISSION (le LLM comprend QUOI faire et POURQUOI)
        # ═══════════════════════════════════════════════════════════
        "mission": (
            f"{p_cfg['mission_prefix']} "
            f"Ton client, {candidate_name}, vise le poste de {job_title} chez {company}. "
            f"Rédige un CV d'une page qui raconte son parcours comme une progression "
            f"logique vers ce poste. Chaque section doit servir le même fil narratif : "
            f"montrer que ce candidat est la réponse naturelle au besoin de l'entreprise."
        ),

        # ═══════════════════════════════════════════════════════════
        # BLOC 2 — LE BRIEF ÉDITORIAL (comment écrire)
        # ═══════════════════════════════════════════════════════════
        "editorial_brief": [
            f"ADOPTE LE PERSONA '{persona}' : Ton {p_cfg['tone']} {p_cfg['focus']}",
            "Construis un RÉCIT de carrière, pas un formulaire. Le lecteur doit voir la trajectoire.",
            f"Mots-clés matchés entre le profil et l'offre : [{matched_kw_str}]. Intègre-les naturellement.",
            f"Domaines métier du candidat : [{domain_str}]. Utilise-les pour ancrer la crédibilité." if domain_str else "",
            "Reformule les expériences en réutilisant le vocabulaire de l'offre quand le profil le justifie.",
            "Chaque bullet raconte une action concrète et son impact — pas un descriptif de poste générique.",
            "Le résumé vend le candidat en 3 phrases : profil → adéquation au poste → valeur ajoutée unique.",
            "Ton : professionnel, direct, technique. Pas de superlatifs vides ni de formulations bateaux.",
            # Seniority Pivot logic
            (
                f"LEVEL OF AUTHORITY: {seniority_level * 100:.0f}%. "
                + (
                    "Utilise des verbes d'action de SÉNIORITÉ / ARCHITECTE (ex: Orchestré, Piloté, Conçu, Optimisé, Expertisé, Structuré) "
                    "pour projeter une forte autorité technique et leadership."
                    if seniority_level > 0.7 else
                    "Utilise des verbes d'action de LEADERSHIP (ex: Piloté, Géré, Coordonné, Amélioré) "
                    "pour projeter une capacité de gestion et d'optimisation."
                    if seniority_level > 0.4 else
                    "Utilise des verbes d'action OPÉRATIONNELS (ex: Réalisé, Développé, Exécuté, Testé) "
                    "pour projeter une efficacité technique directe et concrète."
                )
            ),
            "HR RULE : Focus sur les résultats quantifiables (metrics, %, euros, temps gagné). Un recruteur technique cherche des preuves, pas des descriptions de tâches.",
            "INTERDIT d'utiliser les mots : 'Apprenti', 'Étudiant', 'Élève', 'Élève-Ingénieur', 'en apprentissage'. Remplace systématiquement par 'Ingénieur'. Le headline NE DOIT JAMAIS commencer par 'Élève-Ingénieur'. Présente un expert opérationnel, pas un étudiant.",
            "Utilise EXCLUSIVEMENT les données fournies dans candidate_context. Rien d'inventé, rien de supposé.",
            "Toutes les sorties doivent être en Français.",
        ],

        # ═══════════════════════════════════════════════════════════
        # BLOC 3 — LES GARDES-FOUS (limites techniques en dernier)
        # ═══════════════════════════════════════════════════════════
        "formatting_constraints": build_one_page_constraints(content_cfg),

        # ═══════════════════════════════════════════════════════════
        # DONNÉES D'ENTRÉE
        # ═══════════════════════════════════════════════════════════
        "input_data": {
            "job_offer": job_offer,
            "candidate_context": candidate_context
        },

        # ═══════════════════════════════════════════════════════════
        # FORMAT DE SORTIE ÉPURÉ (Action 4)
        # ═══════════════════════════════════════════════════════════
        "output_format": {
            "cv": {
                "headline": "string",
                "summary": "string (3 phrases)",
                "experiences": [
                    {
                        "id": "string (même id que dans candidate_context.experiences)",
                        "rewritten_title": "string",
                        "bullets": [f"string (action + impact, {content_cfg['max_bullets']} puces)"]
                    }
                ],
                "projects": [
                    {
                        "id": "string (même id que dans candidate_context.ranked_projects)",
                        "rewritten_title": "string",
                        "one_line_description": "string",
                        "keywords_inline": "string — 3 à 4 mots techniques · séparés"
                    }
                ],
                "skills_inline": "string — skills séparés par ' · '"
            }
        }
    }

    # Nettoyer les chaînes vides du brief éditorial
    prompt_dict["editorial_brief"] = [b for b in prompt_dict["editorial_brief"] if b]

    return prompt_dict


def build_skill_extraction_prompt(job_description: str) -> str:
    """Génère un prompt pour extraire les compétences techniques d'une offre d'emploi."""
    return f"""Tu es un expert en recrutement technique et en analyse d'offres d'emploi.

EXTRAIS UNIQUEMENT les compétences techniques (hard skills), outils, logiciels et domaines d'expertise mentionnés dans l'offre ci-dessous.

RÈGLES :
- Retourne une liste simple de termes (ex: Python, Abaqus, CFD, Gestion de projet).
- Sois précis (ex: "Ansys Fluent" au lieu de juste "Logiciel").
- N'inclus PAS de soft skills génériques (ex: "Autonomie", "Rigueur").
- Réponds UNIQUEMENT avec la liste des compétences séparées par des virgules.

DESCRIPTION DU POSTE :
{job_description[:3000]}

COMPÉTENCES EXTRAITES :
"""


# ============================================
# VALIDATION POST-LLM (Action 2)
# ============================================
# Troncature intelligente par phrase au lieu de _truncate_at_word brutal.
# Tolérance souple de 15% : on ne tronque que si le dépassement est significatif.
# Plus de placeholders ("Compétence additionnelle 1") — on log, on ne casse pas.

def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """Coupe à la fin de la dernière phrase complète qui tient dans la limite.

    Préserve le sens du texte en favorisant les coupures naturelles (., !, ?).
    Fallback sur coupure au dernier espace si aucune ponctuation ne tombe dans
    la zone de confort (> 50% du texte conservé).
    """
    if len(text) <= max_chars:
        return text
    candidate = text[:max_chars]
    # Cherche le dernier point/ponctuation AVANT la limite
    last_period = max(candidate.rfind('.'), candidate.rfind('!'), candidate.rfind('?'))
    if last_period > max_chars * 0.5:  # au moins 50% conservé
        return text[:last_period + 1]
    # Fallback : coupe au dernier espace et ferme proprement la phrase
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    # Nettoyage de la dernière ponctuation éventuelle avant de mettre un point
    truncated = __import__('re').sub(r'[^\w\s]$', '', truncated).strip()
    return truncated + "."


def _truncate_at_word(text: str, max_chars: int) -> str:
    """Fallback de troncature simple — conservé pour les champs courts (titres)."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(' ', 1)[0]
    truncated = __import__('re').sub(r'[^\w\s]$', '', truncated).strip()
    return truncated + "."


def validate_llm_output_constraints(cv_data: Dict, content_config: Optional[Dict] = None) -> Dict:
    """Valide et corrige les violations de contraintes One-Page.

    Action 2 — Validation souple :
    - Tolérance de 15% avant troncature effective
    - Troncature par phrase (`_truncate_at_sentence`) pour les textes longs
    - Troncature par mot (`_truncate_at_word`) pour les champs courts (titres)
    - Plus de placeholders pour les skills manquants
    - Les dépassements légers sont loggés mais pas corrigés
    """
    cfg = {**DEFAULT_CONTENT_CONFIG, **(content_config or {})}
    violations = []
    if "cv" not in cv_data:
        return {"cv_data": cv_data, "violations": ["Missing 'cv' key"], "had_violations": True}

    cv = cv_data["cv"]

    # 1. Headline — accepte string direct OU {value, char_count}
    headline_obj = cv.get("headline", {})
    headline = headline_obj.get("value", "") if isinstance(headline_obj, dict) else str(headline_obj)
    hard_limit_headline = int(cfg["headline_max_chars"] * SOFT_TOLERANCE_RATIO)
    if len(headline) > hard_limit_headline:
        headline = _truncate_at_word(headline, cfg["headline_max_chars"])
        violations.append({"field": "headline", "action": "truncated"})
    elif len(headline) > cfg["headline_max_chars"]:
        violations.append({"field": "headline", "action": "soft_over", "by": len(headline) - cfg["headline_max_chars"]})
    cv["headline"] = {"value": headline, "char_count": len(headline)}

    # 2. Summary — troncature par phrase pour garder le sens
    summary_obj = cv.get("summary", {})
    summary = summary_obj.get("value", "") if isinstance(summary_obj, dict) else str(summary_obj)
    hard_limit_summary = int(cfg["summary_max_chars"] * SOFT_TOLERANCE_RATIO)
    if len(summary) > hard_limit_summary:
        summary = _truncate_at_sentence(summary, cfg["summary_max_chars"])
        violations.append({"field": "summary", "action": "truncated"})
    elif len(summary) > cfg["summary_max_chars"]:
        violations.append({"field": "summary", "action": "soft_over", "by": len(summary) - cfg["summary_max_chars"]})
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
        hard_limit_bullet = int(cfg["max_bullet_chars"] * SOFT_TOLERANCE_RATIO)
        for j, bullet in enumerate(bullets):
            if len(bullet) > hard_limit_bullet:
                # Troncature par phrase pour les bullets longs
                bullets[j] = _truncate_at_sentence(bullet, cfg["max_bullet_chars"])
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "truncated"})
            elif len(bullet) > cfg["max_bullet_chars"]:
                violations.append({"field": f"exp[{i}].bullet[{j}]", "action": "soft_over", "by": len(bullet) - cfg["max_bullet_chars"]})
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
        hard_limit_title = int(cfg["project_title_max_chars"] * SOFT_TOLERANCE_RATIO)
        if len(title) > hard_limit_title:
            proj["rewritten_title"] = _truncate_at_word(title, cfg["project_title_max_chars"])
            violations.append({"field": f"proj[{i}].title", "action": "truncated"})
        elif len(title) > cfg["project_title_max_chars"]:
            violations.append({"field": f"proj[{i}].title", "action": "soft_over", "by": len(title) - cfg["project_title_max_chars"]})

        desc = proj.get("one_line_description", "")
        hard_limit_desc = int(cfg["project_desc_max_chars"] * SOFT_TOLERANCE_RATIO)
        if len(desc) > hard_limit_desc:
            proj["one_line_description"] = _truncate_at_sentence(desc, cfg["project_desc_max_chars"])
            violations.append({"field": f"proj[{i}].desc", "action": "truncated"})
        elif len(desc) > cfg["project_desc_max_chars"]:
            violations.append({"field": f"proj[{i}].desc", "action": "soft_over", "by": len(desc) - cfg["project_desc_max_chars"]})
    cv["projects"] = projs

    # 5. Skills inline (Min/Max) — accepts · or • as separators, normalises to ·
    #    Action 2 : plus de placeholder "Compétence additionnelle" — on log seulement
    skills_inline = cv.get("skills_inline", "")
    if isinstance(skills_inline, str) and skills_inline.strip():
        skills = [s.strip() for s in re.split(r"\s*[·•]\s*", skills_inline) if s.strip()]
        if len(skills) > cfg["skills_count"]:
            skills = skills[: cfg["skills_count"]]
            violations.append({"field": "skills_inline", "action": "cut_to_max"})
        if len(skills) < cfg["skills_min"]:
            violations.append({"field": "skills_inline", "action": "below_min_unfilled"})
        cv["skills_inline"] = " · ".join(skills)

    cv_data["cv"] = cv
    return {"cv_data": cv_data, "violations": violations, "had_violations": len(violations) > 0}


def post_process_llm_output(raw_output: Dict, content_config: Optional[Dict] = None) -> Dict:
    """Valide les contraintes sans remplacement automatique de mots."""
    from pydantic import ValidationError
    from engine.schemas import LLMOutput
    try:
        LLMOutput.model_validate(raw_output)
    except ValidationError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur de validation Pydantic de la sortie LLM : {e}")
        # On ne bloque pas brutalement pour laisser la logique fallback de cv_generator.py jouer,
        # mais la validation Pydantic lèvera une exception qui sera catchée par cv_generator.py (try/except fallback).
        raise ValueError(f"Sortie LLM invalide selon le schéma strict : {e}")
        
    return validate_llm_output_constraints(raw_output, content_config=content_config)
