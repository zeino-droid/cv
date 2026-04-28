"""
🎯 SECTION REWRITE — Édition ciblée pilotée par l'IA, section par section.

Pour chaque section éditable du CV, ce module :
  1. Récupère la donnée d'origine du profil maître (source).
  2. Récupère le rendu actuel du CV (current).
  3. Construit un prompt spécialisé (par section) avec source + offre + instruction.
  4. Parse le résultat selon le type attendu (str | List[str] | str avec séparateur ·).
  5. Renvoie (valeur_typée, message_erreur).

Le résultat est stocké dans `gen_state["section_overrides"][section_key]` puis
réinjecté dans `cv_generator.generate_one_page_cv(section_overrides=...)`.

─────────────────────────────────────────────────────────────────────────────
SÉPARATION DES RESPONSABILITÉS DANS LE PIPELINE
─────────────────────────────────────────────────────────────────────────────
• Génération (cv_generator.generate_one_page_cv)
    Produit une version complète neuve à partir du profil brut et de l'offre.
    Ne touche pas aux section_overrides existants.

• Amélioration (ce module — section_rewrite)
    Modifie UNIQUEMENT la section ciblée par l'utilisateur (un delta).
    Travaille sur le CV déjà rendu (current) + la source du profil maître.
    N'appelle jamais generate_one_page_cv en interne.

• Recompilation (cv_generator.generate_one_page_cv avec section_overrides)
    Réassemble le CV en appliquant les overrides sans rappeler le LLM.
    Garantit que seules les sections explicitement surchargées changent.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# 1. Catalogue des sections éditables
# ============================================================
# Chaque entrée décrit comment :
#   - étiqueter la section dans l'UI (label, icon)
#   - expliquer son rôle au LLM (prompt_role)
#   - typer la valeur attendue (value_type)
#   - imposer des limites de format (max_chars, max_items, max_item_chars)
#   - éventuellement cibler un item par id (per_item=True → expérience par expérience)

EDITABLE_SECTIONS: Dict[str, Dict[str, Any]] = {
    "headline": {
        "icon": "🎯",
        "label": "Accroche (titre du CV)",
        "value_type": "str",
        "max_chars": 110,
        "per_item": False,
        "prompt_role": (
            "accroche professionnelle (headline) qui apparaît juste sous le nom "
            "sur la première ligne du CV. Une seule phrase courte, percutante, "
            "qui positionne le candidat sur l'offre."
        ),
        "format_rules": (
            "- Une seule ligne, 110 caractères MAX.\n"
            "- Formulation naturelle et fluide (style titre ou mini-phrase accepté).\n"
            "- Inclure idéalement 1 mot-clé fort de l'offre."
        ),
    },
    "summary": {
        "icon": "📝",
        "label": "Résumé professionnel",
        "value_type": "str",
        "max_chars": 400,
        "per_item": False,
        "prompt_role": (
            "résumé professionnel (3-4 lignes, ~400 caractères) en haut du CV. "
            "Vendre la candidature en montrant l'adéquation au poste."
        ),
        "format_rules": (
            "- 3 à 4 phrases, 400 caractères MAX.\n"
            "- Français professionnel, ton humain et crédible.\n"
            "- Intégrer 1 à 3 mots-clés explicites de l'offre quand c'est pertinent."
        ),
    },
    "achievements": {
        "icon": "💼",
        "label": "Puces d'une expérience",
        "value_type": "list_str",
        "max_items": 2,
        "max_item_chars": 180,
        "per_item": True,  # nécessite un exp_id
        "prompt_role": (
            "puces d'accomplissement (bullets) pour UNE expérience pro précise. "
            "Chaque puce raconte un Action+Résultat aligné sur l'offre."
        ),
        "format_rules": (
            "- Jusqu'à 2 puces, 180 caractères MAX par puce.\n"
            "- Décrire des contributions concrètes avec un style naturel.\n"
            "- Les verbes d'action sont recommandés mais pas imposés.\n"
            "- Réutiliser les mots de l'offre quand cela apporte de la clarté."
        ),
    },
    "project_description": {
        "icon": "🚀",
        "label": "Description d'un projet",
        "value_type": "str",
        "max_chars": 150,
        "per_item": True,  # nécessite un proj_id
        "prompt_role": (
            "description courte (1 ligne) d'UN projet académique. Doit montrer "
            "l'angle pertinent pour l'offre."
        ),
        "format_rules": (
            "- 1 phrase, 150 caractères MAX.\n"
            "- Formulation libre, claire et orientée valeur."
        ),
    },
    "project_keywords": {
        "icon": "🏷️",
        "label": "Mots-clés d'un projet",
        "value_type": "str_dot_separated",
        "max_items": 6,
        "max_item_chars": 25,
        "per_item": True,
        "prompt_role": (
            "mots-clés techniques d'UN projet, séparés par ' · '. "
            "Doivent maximiser le matching ATS avec l'offre."
        ),
        "format_rules": (
            "- 4 à 6 mots-clés MAX, séparés par ' · '.\n"
            "- 1-3 mots par item.\n"
            "- Privilégier les termes utiles pour le poste, sans forçage artificiel."
        ),
    },
    "skills_hard": {
        "icon": "🛠️",
        "label": "Compétences techniques",
        "value_type": "list_str",
        "max_items": 12,
        "max_item_chars": 30,
        "per_item": False,
        "prompt_role": (
            "liste des compétences techniques (logiciels, langages, outils) "
            "à afficher dans la section 'Compétences Techniques' du CV."
        ),
        "format_rules": (
            "- 8 à 12 items MAX.\n"
            "- Garder les compétences vraiment utiles, y compris les fondamentaux transverses.\n"
            "- Conserve les noms tels qu'ils apparaissent dans le profil source."
        ),
    },
    "skills_domain": {
        "icon": "🧠",
        "label": "Connaissances métier",
        "value_type": "list_str",
        "max_items": 6,
        "max_item_chars": 60,
        "per_item": False,
        "prompt_role": (
            "domaines d'expertise / connaissances métier "
            "(ex: 'Modélisation thermique', 'CFD', 'Jumeaux numériques')."
        ),
        "format_rules": (
            "- 3 à 6 items MAX.\n"
            "- Reformule pour matcher le vocabulaire de l'offre.\n"
            "- Item court (2-5 mots)."
        ),
    },
    "skills_soft": {
        "icon": "🤝",
        "label": "Savoir-être",
        "value_type": "list_str",
        "max_items": 5,
        "max_item_chars": 50,
        "per_item": False,
        "prompt_role": (
            "soft skills présentés sur le CV. Doivent répondre aux attentes "
            "implicites/explicites de l'offre."
        ),
        "format_rules": (
            "- 3 à 5 items MAX.\n"
            "- Item court (1-4 mots)."
        ),
    },
    "letter": {
        "icon": "✉️",
        "label": "Lettre de motivation",
        "value_type": "str",
        "max_chars": 2500,
        "per_item": False,
        "prompt_role": (
            "lettre de motivation complète en français, structurée en 3-4 paragraphes "
            "(intro / valeur ajoutée / motivation / call-to-action)."
        ),
        "format_rules": (
            "- Garde l'en-tête et la signature s'ils existent.\n"
            "- Ton pro mais incarné (1ère personne).\n"
            "- 250-400 mots."
        ),
    },
}


def list_section_keys(per_item_only: bool = False) -> List[str]:
    """Liste les clés de section éditables."""
    if per_item_only:
        return [k for k, v in EDITABLE_SECTIONS.items() if v.get("per_item")]
    return list(EDITABLE_SECTIONS.keys())


# ============================================================
# 2. Extraction de la donnée SOURCE (profil maître)
# ============================================================
def extract_source(
    profile: Dict, section_key: str, item_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Récupère la donnée d'origine du profil maître pour la section donnée.
    Renvoie un dict {label, raw, json_dump} pour affichage UI + LLM.
    """
    if section_key == "headline":
        # On retourne tous les headlines des profils cibles (pour donner du contexte)
        profiles = profile.get("profiles", {})
        items = {pid: p.get("headline", "") for pid, p in profiles.items()}
        items["__default__"] = profile.get("personal_info", {}).get("headline_default", "")
        return {
            "label": "Accroches disponibles dans le profil maître",
            "raw": items,
            "json_dump": json.dumps(items, ensure_ascii=False, indent=2),
        }

    if section_key == "summary":
        return {
            "label": "Résumé par défaut du profil",
            "raw": profile.get("personal_info", {}).get("summary_default", ""),
            "json_dump": profile.get("personal_info", {}).get("summary_default", ""),
        }

    if section_key == "achievements":
        if not item_id:
            return {"label": "—", "raw": None, "json_dump": ""}
        exps = profile.get("experience_stark") or profile.get("experiences", [])
        for exp in exps:
            if exp.get("id") == item_id:
                # On donne tout le STAR-K pour que l'IA puisse reformuler proprement
                source = {
                    "id": exp.get("id"),
                    "title": exp.get("title"),
                    "company": exp.get("company"),
                    "period": exp.get("period"),
                    "Situation": exp.get("S", ""),
                    "Tache": exp.get("T", ""),
                    "Action": exp.get("A", ""),
                    "Resultat": exp.get("R", ""),
                    "Keywords": exp.get("K", []),
                }
                return {
                    "label": f"Expérience source : {exp.get('title')} — {exp.get('company')}",
                    "raw": source,
                    "json_dump": json.dumps(source, ensure_ascii=False, indent=2),
                }
        return {"label": f"Expérience '{item_id}' introuvable", "raw": None, "json_dump": ""}

    if section_key in ("project_description", "project_keywords"):
        if not item_id:
            return {"label": "—", "raw": None, "json_dump": ""}
        exps = profile.get("experience_stark") or profile.get("experiences", [])
        for exp in exps:
            if exp.get("id") == item_id:
                source = {
                    "id": exp.get("id"),
                    "title": exp.get("title"),
                    "Description": exp.get("D", "") or exp.get("A", ""),
                    "Keywords": exp.get("K", []),
                    "Situation": exp.get("S", ""),
                    "Resultat": exp.get("R", ""),
                }
                return {
                    "label": f"Projet source : {exp.get('title')}",
                    "raw": source,
                    "json_dump": json.dumps(source, ensure_ascii=False, indent=2),
                }
        return {"label": f"Projet '{item_id}' introuvable", "raw": None, "json_dump": ""}

    if section_key == "skills_hard":
        items = profile.get("skills_taxonomy", {}).get("hard_skills", [])
        return {
            "label": "Hard skills du profil maître (avec contexte)",
            "raw": items,
            "json_dump": json.dumps(items, ensure_ascii=False, indent=2),
        }

    if section_key == "skills_domain":
        items = profile.get("skills_taxonomy", {}).get("domain_knowledge", [])
        return {
            "label": "Connaissances métier du profil maître",
            "raw": items,
            "json_dump": json.dumps(items, ensure_ascii=False, indent=2),
        }

    if section_key == "skills_soft":
        items = profile.get("skills_taxonomy", {}).get("soft_skills", [])
        return {
            "label": "Soft skills du profil maître",
            "raw": items,
            "json_dump": json.dumps(items, ensure_ascii=False, indent=2),
        }

    if section_key == "letter":
        return {
            "label": "(la lettre n'a pas de 'source' dans le profil — on retravaille la version actuelle)",
            "raw": "",
            "json_dump": "",
        }

    return {"label": "—", "raw": None, "json_dump": ""}


# ============================================================
# 3. Extraction de la valeur ACTUELLE (rendu CV courant)
# ============================================================
def extract_current(
    cv_data: Dict, section_key: str, item_id: Optional[str] = None
) -> Any:
    """
    Récupère la valeur actuellement affichée dans le CV pour la section.
    """
    if section_key == "headline":
        return cv_data.get("headline", "")
    if section_key == "summary":
        return cv_data.get("summary", "")
    if section_key == "achievements":
        for exp in cv_data.get("experiences", []):
            # Le CV courant n'a pas d'id ; on matche par titre source via item_id
            # → l'UI doit passer le title pour matcher si pas d'id
            if exp.get("id") == item_id or exp.get("position") == item_id:
                return exp.get("achievements", [])
        return []
    if section_key == "project_description":
        for p in cv_data.get("projects", []):
            if p.get("id") == item_id or p.get("name") == item_id:
                return p.get("description", "")
        return ""
    if section_key == "project_keywords":
        for p in cv_data.get("projects", []):
            if p.get("id") == item_id or p.get("name") == item_id:
                return p.get("keywords", "")
        return ""
    if section_key == "skills_hard":
        return [
            s.get("name", "")
            for s in cv_data.get("grouped_skills", {}).get("Compétences Techniques", [])
        ]
    if section_key == "skills_domain":
        return [
            s.get("name", "")
            for s in cv_data.get("grouped_skills", {}).get("Connaissances Métier", [])
        ]
    if section_key == "skills_soft":
        return [
            s.get("name", "")
            for s in cv_data.get("grouped_skills", {}).get("Savoir-être", [])
        ]
    if section_key == "letter":
        # La lettre n'est pas dans cv_data ; le caller doit la passer via cv_data["letter_text"]
        # OU appeler extract_current avec un cv_data enrichi par gen_state["letter_text"].
        return cv_data.get("letter_text", "")
    return None


def list_experience_items(cv_data: Dict) -> List[Dict[str, str]]:
    """
    Liste les expériences actuellement dans le CV (pour le sélecteur UI).
    Renvoie [{id, label}] où label = 'Titre — Entreprise'.
    """
    out = []
    for i, exp in enumerate(cv_data.get("experiences", [])):
        eid = exp.get("id") or exp.get("position") or f"exp_{i}"
        label = f"{exp.get('position', '?')} — {exp.get('company', '?')}"
        out.append({"id": eid, "label": label})
    return out


def list_project_items(cv_data: Dict) -> List[Dict[str, str]]:
    """Liste les projets actuellement dans le CV."""
    out = []
    for i, p in enumerate(cv_data.get("projects", [])):
        pid = p.get("id") or p.get("name") or f"proj_{i}"
        label = p.get("name", "?")
        out.append({"id": pid, "label": label})
    return out


def find_unapplied_overrides(
    cv_data: Dict, section_overrides: Dict[str, Any]
) -> List[str]:
    """Repère les overrides per-item dont l'id n'est plus dans le CV courant.

    Renvoie une liste de messages humains lisibles, ex :
      "Puces d'expérience pour 'AM_PFE' (non présent dans le CV courant)".
    Utilisé par l'UI pour afficher un warning et éviter l'effet
    "j'ai cliqué Appliquer mais rien ne change".
    """
    if not section_overrides:
        return []
    msgs: List[str] = []
    exp_ids = {e.get("id") for e in cv_data.get("experiences", []) if e.get("id")}
    proj_ids = {p.get("id") for p in cv_data.get("projects", []) if p.get("id")}

    ach = section_overrides.get("achievements") or {}
    for eid in ach:
        if eid not in exp_ids:
            msgs.append(f"Puces d'expérience pour « {eid} » (non présent dans le CV courant)")

    desc = section_overrides.get("project_description") or {}
    for pid in desc:
        if pid not in proj_ids:
            msgs.append(f"Description du projet « {pid} » (non présent dans le CV courant)")

    kw = section_overrides.get("project_keywords") or {}
    for pid in kw:
        if pid not in proj_ids:
            msgs.append(f"Mots-clés du projet « {pid} » (non présent dans le CV courant)")

    return msgs


# ============================================================
# 4. Construction du prompt spécialisé
# ============================================================
def build_section_prompt(
    section_key: str,
    source: Dict[str, Any],
    current: Any,
    job: Dict[str, Any],
    instruction: str,
) -> str:
    """
    Construit le prompt envoyé au LLM pour réécrire UNE section ciblée.
    """
    spec = EDITABLE_SECTIONS.get(section_key, {})
    role = spec.get("prompt_role", "")
    rules = spec.get("format_rules", "")
    value_type = spec.get("value_type", "str")

    job_ctx = (
        f"INTITULÉ : {job.get('title', '')}\n"
        f"ENTREPRISE : {job.get('company', '')}\n"
        f"LIEU : {job.get('location', '')}\n"
        f"COMPÉTENCES MATCHÉES : {', '.join((job.get('matched_skills') or [])[:8])}\n"
        f"DESCRIPTION (extrait) :\n{(job.get('description') or '')[:1500]}"
    )

    if value_type == "list_str":
        current_str = "\n".join(f"- {x}" for x in (current or []))
        output_format = (
            'JSON strict : {"items": ["puce 1", "puce 2", ...]} — RIEN d\'autre.'
        )
    elif value_type == "str_dot_separated":
        current_str = current or ""
        output_format = (
            "Une seule ligne avec des items séparés par ' · ' — RIEN d'autre."
        )
    else:  # str
        current_str = current or ""
        output_format = "Le texte réécrit, en clair, sans préambule ni guillemets."

    source_label = source.get("label", "")
    source_dump = source.get("json_dump", "")

    return f"""Tu es un expert en rédaction de CV/lettres pour ingénieurs en France.
Tu vas réécrire UNE SECTION ciblée du CV en t'appuyant sur la donnée source du profil
et sur l'offre d'emploi visée.

═══════════════════════════════════════════
SECTION À RÉÉCRIRE : {spec.get('label', section_key)}
RÔLE DE LA SECTION : {role}
═══════════════════════════════════════════

DONNÉE SOURCE DU PROFIL ({source_label}) :
{source_dump}

VERSION ACTUELLEMENT AFFICHÉE :
{current_str if current_str else '(vide)'}

OFFRE VISÉE :
{job_ctx}

INSTRUCTION DE L'UTILISATEUR :
{instruction}

RÈGLES DE FORMAT :
{rules}

FORMAT DE SORTIE :
{output_format}
"""


# ============================================================
# 5. Parsing du résultat selon le type attendu
# ============================================================
def _parse_list_json(raw: str, max_items: int, max_item_chars: int) -> List[str]:
    """Parse un JSON {"items": [...]}, fallback sur split par ligne."""
    cleaned = re.sub(r"```json\s*|\s*```", "", raw).strip()
    # Essai JSON
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "items" in obj:
            items = obj["items"]
        elif isinstance(obj, list):
            items = obj
        else:
            items = []
    except (json.JSONDecodeError, ValueError):
        # Fallback : split par ligne, retire bullets
        items = []
        for line in cleaned.split("\n"):
            s = line.strip().lstrip("-•*").strip()
            if s:
                items.append(s)
    out = []
    for it in items[:max_items]:
        if not isinstance(it, str):
            it = str(it)
        out.append(it.strip()[:max_item_chars])
    return [x for x in out if x]


def parse_section_value(
    section_key: str, raw_text: str
) -> Tuple[Any, Optional[str]]:
    """
    Parse le texte renvoyé par le LLM selon le type attendu pour cette section.
    Renvoie (valeur_typée, message_erreur).
    """
    spec = EDITABLE_SECTIONS.get(section_key, {})
    value_type = spec.get("value_type", "str")
    max_chars = spec.get("max_chars")
    max_items = spec.get("max_items")
    max_item_chars = spec.get("max_item_chars", 200)

    raw = (raw_text or "").strip()
    if not raw:
        return None, "Réponse vide du LLM."

    if value_type == "list_str":
        items = _parse_list_json(raw, max_items or 3, max_item_chars)
        if not items:
            return None, "Aucun item parseable dans la réponse du LLM."
        return items, None

    if value_type == "str_dot_separated":
        # Nettoyage : retirer guillemets/préambule/markdown
        cleaned = re.sub(r"```.*?\n|```", "", raw, flags=re.DOTALL).strip()
        cleaned = cleaned.strip("\"'`")
        # Si le LLM a renvoyé du JSON, on extrait
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, list):
                cleaned = " · ".join(str(x) for x in obj)
            elif isinstance(obj, dict) and "items" in obj:
                cleaned = " · ".join(str(x) for x in obj["items"])
        except (json.JSONDecodeError, ValueError):
            pass
        # Garde la première ligne uniquement
        cleaned = cleaned.split("\n")[0].strip()
        # Force le séparateur ' · ' si on voit ',' ou ';'
        if " · " not in cleaned and ("," in cleaned or ";" in cleaned):
            parts = re.split(r"[,;]", cleaned)
            cleaned = " · ".join(p.strip() for p in parts if p.strip())
        # Cap au nombre max d'items
        items = [p.strip() for p in cleaned.split("·") if p.strip()]
        items = items[: max_items or 6]
        items = [it[:max_item_chars] for it in items]
        return " · ".join(items), None

    # value_type == "str"
    cleaned = raw.strip("\"'`").strip()
    # Retire un éventuel préambule type "Voici la réécriture :"
    cleaned = re.sub(r"^(voici|voilà|here)[^:\n]{0,40}:\s*", "", cleaned, flags=re.IGNORECASE)
    if max_chars:
        cleaned = cleaned[: max_chars + 50]  # léger dépassement toléré, on coupe pas brutalement
    return cleaned, None


# ============================================================
# 6. Orchestrateur de haut niveau
# ============================================================
async def rewrite_section(
    llm,
    *,
    section_key: str,
    profile: Dict,
    cv_data: Dict,
    job: Dict,
    instruction: str,
    item_id: Optional[str] = None,
    temperature: float = 0.4,
) -> Tuple[Any, Optional[str]]:
    """
    Bout-en-bout : extract_source → build_prompt → llm.generate → parse.
    Renvoie (valeur_typée, message_erreur). En cas d'échec, valeur=None.
    """
    if section_key not in EDITABLE_SECTIONS:
        return None, f"Section inconnue : {section_key}"

    if not instruction or not instruction.strip():
        return None, "Instruction vide — précise ce que tu veux améliorer."

    spec = EDITABLE_SECTIONS[section_key]
    if spec.get("per_item") and not item_id:
        return None, f"Cette section ('{spec.get('label')}') nécessite de choisir un item."

    if llm is None:
        return None, "Aucun moteur LLM disponible. Vérifie GEMINI_API_KEY."

    source = extract_source(profile, section_key, item_id=item_id)
    current = extract_current(cv_data, section_key, item_id=item_id)
    prompt = build_section_prompt(
        section_key=section_key,
        source=source,
        current=current,
        job=job,
        instruction=instruction,
    )

    try:
        raw = await llm.generate(prompt, temperature=temperature)
    except Exception as exc:
        return None, f"Erreur LLM : {exc}"

    if raw is None:
        msg = (
            getattr(llm, "last_error_message", None)
            or "Le moteur LLM n'a renvoyé aucun texte."
        )
        return None, msg

    return parse_section_value(section_key, raw)
