"""
Module ranking partagé — scoring heuristique + Gemini rerank/expansion/extraction.

Récupère et adapte la logique éprouvée de l'ancien sourcing_advanced.py :
  - Alias de compétences (FEM = EF = Éléments Finis = FEA…)
  - Scoring (skills, premium keywords, location, freshness)
  - Filtre stage/alternance sur le TITRE uniquement
  - Fallback top-25 si min_score filtre tout
  - Gemini : expansion sémantique des mots-clés, rerank profond, extraction skills
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).parent.parent.parent
LLM_CACHE_PATH = ROOT / "storage" / "llm_expansion_cache.json"
LLM_CACHE_TTL_DAYS = 7

# Alias de compétences — toutes les variantes pointent vers le même concept
SKILL_ALIASES: Dict[str, List[str]] = {
    "éléments finis": ["ef", "fem", "fea", "elements finis", "éléments-finis", "finite element"],
    "cfd": ["computational fluid dynamics", "fluide numérique", "simulation fluide"],
    "ansys fluent": ["fluent", "ansys cfd"],
    "ansys workbench / apdl": ["ansys workbench", "workbench", "ansys apdl", "apdl", "ansys mechanical", "ansys structure"],
    "abaqus": ["abaqus/cae", "abaqus cae", "abaqus/explicit", "abaqus/standard"],
    "python": ["python3", "scripting python", "dev python"],
    "jumeau numérique": ["digital twin", "twin numérique", "modèle numérique temps réel"],
    "modélisation thermique": ["thermique numérique", "simulation thermique", "calcul thermique"],
    "matlab": ["matlab/simulink", "simulink", "matlab simulink"],
    "metafor": ["metafor fem"],
    "thermomécanique": ["thermo-mécanique", "thermomecanique", "couplage thermomécanique"],
    "rdm": ["résistance des matériaux", "resistance des materiaux"],
    "calcul de structures": ["calcul structure", "calculs de structures", "structural analysis"],
}


# ──────────────────────────────────────────────────────────────────
#  GEMINI HELPERS
# ──────────────────────────────────────────────────────────────────

def _gemini_client():
    try:
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        return genai.Client(api_key=key)
    except Exception:
        return None


def has_gemini() -> bool:
    return _gemini_client() is not None


def _gemini_call(
    prompt: str,
    max_tokens: int = 800,
    model: str = "gemini-flash-latest",
    retries: int = 2,
) -> Optional[str]:
    client = _gemini_client()
    if client is None:
        return None
    for attempt in range(retries + 1):
        try:
            from google.genai import types
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=max_tokens,
                ),
            )
            return (resp.text or "").strip()
        except Exception as exc:
            err = str(exc).lower()
            retryable = any(k in err for k in ("429", "rate", "quota", "timeout", "503", "overloaded"))
            if retryable and attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            print(f"   ⚠️  Gemini error: {exc}")
            return None
    return None


# ──────────────────────────────────────────────────────────────────
#  CACHE LLM (expansion sémantique)
# ──────────────────────────────────────────────────────────────────

def _load_llm_cache() -> Dict:
    try:
        if LLM_CACHE_PATH.exists():
            with open(LLM_CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_llm_cache(cache: Dict) -> None:
    try:
        LLM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LLM_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"   ⚠️  Impossible de sauvegarder le cache LLM: {exc}")


def _cache_key(keywords: List[str]) -> str:
    raw = "|".join(sorted(k.lower().strip() for k in keywords))
    return hashlib.md5(raw.encode()).hexdigest()


# ──────────────────────────────────────────────────────────────────
#  EXPANSION SÉMANTIQUE DES MOTS-CLÉS
# ──────────────────────────────────────────────────────────────────

def expand_keywords_with_llm(
    keywords: List[str],
    profile: Dict,
    max_extra_per_keyword: int = 2,
) -> List[str]:
    """Élargit les mots-clés via Gemini (cache 7 j)."""
    if not keywords:
        return []

    cache = _load_llm_cache()
    key = _cache_key(keywords)
    entry = cache.get(key)
    if entry:
        cached_date = datetime.fromisoformat(entry.get("date", "2000-01-01")).date()
        if (date.today() - cached_date).days < LLM_CACHE_TTL_DAYS:
            return entry.get("expanded", list(keywords))

    domain = profile.get("personal_info", {}).get("headline_default", "")
    summary = profile.get("personal_info", {}).get("summary_default", "")

    prompt = f"""Tu es un recruteur expert en France. Voici un profil candidat :
HEADLINE: {domain}
RÉSUMÉ: {summary}

Voici ses mots-clés de recherche actuels :
{chr(10).join(f"- {k}" for k in keywords)}

Génère pour CHAQUE mot-clé jusqu'à {max_extra_per_keyword} variantes sémantiques pertinentes.
IMPORTANT : Les variantes doivent être en FRANÇAIS (les recruteurs français utilisent des termes français).
Réponds UNIQUEMENT au format JSON strict : {{"keyword_original": ["variante1", "variante2"]}}.
Pas de texte autour, pas de markdown.
"""
    raw = _gemini_call(prompt, max_tokens=1200)
    if not raw:
        return list(keywords)

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
    except Exception:
        return list(keywords)

    expanded: List[str] = []
    seen = set()
    for kw in keywords:
        for variant in [kw] + list(data.get(kw, []))[:max_extra_per_keyword]:
            v = (variant or "").strip()
            kv = v.lower()
            if v and kv not in seen:
                seen.add(kv)
                expanded.append(v)

    cache[key] = {"date": date.today().isoformat(), "expanded": expanded}
    _save_llm_cache(cache)
    return expanded


# ──────────────────────────────────────────────────────────────────
#  DÉDUPLICATION
# ──────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def _signature(job: Dict):
    title = _normalize(job.get("title", ""))
    company = _normalize(job.get("company", ""))
    city = _normalize((job.get("location") or "").split(",")[0])
    base = f"{title}@{company}@{city}"
    tokens = set(re.findall(r"\w+", title))
    return base, tokens


def deduplicate_smart(jobs: List[Dict]) -> List[Dict]:
    """Dédup multi-niveaux : URL / hash strict / Jaccard ≥ 0.75 par entreprise."""
    seen_urls: set = set()
    seen_keys: set = set()
    bucket: Dict[str, List[set]] = {}
    out: List[Dict] = []

    for job in jobs:
        url = (job.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        base, tokens = _signature(job)
        if base in seen_keys:
            continue

        company = (job.get("company") or "").lower().strip()
        is_dup = False
        for existing in bucket.get(company, []):
            inter = len(tokens & existing)
            union = len(tokens | existing) or 1
            if inter / union >= 0.75:
                is_dup = True
                break
        if is_dup:
            continue

        seen_keys.add(base)
        bucket.setdefault(company, []).append(tokens)
        out.append(job)
    return out


# ──────────────────────────────────────────────────────────────────
#  SCORING HEURISTIQUE
# ──────────────────────────────────────────────────────────────────

def _build_skill_variants(skill_name: str) -> List[str]:
    name_lower = skill_name.lower().strip()
    variants = {name_lower}
    for canonical, aliases in SKILL_ALIASES.items():
        if name_lower == canonical or name_lower in aliases:
            variants.add(canonical)
            variants.update(aliases)
    return list(variants)


def _freshness_bonus(posted_date: str) -> int:
    if not posted_date:
        return 0
    try:
        d = datetime.strptime(posted_date[:10], "%Y-%m-%d").date()
        delta = (date.today() - d).days
        if delta <= 2: return 8
        if delta <= 7: return 5
        if delta <= 14: return 2
        return 0
    except Exception:
        return 0


def score_job(job: Dict, profile: Dict, config: Dict) -> Dict:
    """Scoring heuristique V2 — plus discriminant, plus intelligent.

    Changements clés vs V1 :
      - Base score réduit (10 au lieu de 20) pour une meilleure discrimination
      - Skill matching pondéré : titre > description
      - Title Relevance Score : bonus/malus basé sur la densité technique du titre
      - Bonus explicite CDI, junior-friendly
      - TF-IDF léger : similarité textuelle profil → description (sans LLM)
      - Plafond 95% (100 réservé au manual override)
    """
    scoring = config.get("scoring", {})
    score = scoring.get("base_score", 10)
    title_lower = (job.get("title") or "").lower()
    desc_lower = (job.get("description") or "").lower()
    haystack = f"{title_lower} {desc_lower}"

    taxonomy = profile.get("skills_taxonomy", {})
    profile_skills: List[str] = []
    for skill in taxonomy.get("hard_skills", []):
        profile_skills.append(skill.get("name", ""))
    profile_skills.extend(taxonomy.get("domain_knowledge", []))

    matched: List[str] = []
    title_matches = 0

    # --- Phase 1 : Skill matching pondéré ---
    TITLE_MATCH_BONUS = 15   # Skill trouvé dans le TITRE (très fort signal)
    DESC_MATCH_BONUS = 5     # Skill trouvé dans la description (signal modéré)
    for skill in profile_skills:
        if not skill:
            continue
        variants = _build_skill_variants(skill)
        in_title = any(v in title_lower for v in variants)
        in_desc = any(v in haystack for v in variants)
        if in_title:
            matched.append(skill)
            score += TITLE_MATCH_BONUS
            title_matches += 1
        elif in_desc:
            matched.append(skill)
            score += DESC_MATCH_BONUS

    # --- Phase 2 : Premium keywords ---
    for kw, bonus in scoring.get("premium_keywords", {}).items():
        if str(kw).lower() in haystack:
            score += int(bonus)

    # --- Phase 3 : Location bonus ---
    loc = (job.get("location") or "").lower()
    for zone in scoring.get("preferred_locations", []):
        if zone in loc:
            score += scoring.get("location_bonus", 5)
            break

    # --- Phase 4 : Title Relevance (pénalise les titres trop génériques) ---
    TECH_TITLE_KEYWORDS = {
        "simulation", "calcul", "cfd", "thermique", "mécanique", "numérique",
        "modélisation", "éléments finis", "r&d", "recherche", "développement",
        "énergie", "ingénieur", "engineer", "fea", "fem", "abaqus", "ansys",
        "fluent", "python", "matlab", "composites", "structures", "matériaux",
        "dimensionnement", "bureau d'études", "be", "conception",
    }
    title_tokens = set(title_lower.split())
    title_tech_hits = sum(1 for kw in TECH_TITLE_KEYWORDS if kw in title_lower)

    if title_tech_hits == 0:
        score -= 8   # Titre complètement générique (ex: "Consultant")
    elif title_tech_hits >= 3:
        score += 6   # Titre très technique et ciblé

    # --- Phase 5 : Junior / Jeune diplômé friendly ---
    JD_KEYWORDS = {"débutant", "junior", "jeune diplômé", "jeune diplome",
                   "première expérience", "sans expérience", "jeune ingénieur",
                   "graduate", "entry level", "recent graduate"}
    if any(kw in haystack for kw in JD_KEYWORDS):
        score += 8

    # --- Phase 6 : CDI explicite ---
    if "cdi" in title_lower or "cdi" in desc_lower[:200]:
        score += 3

    # --- Phase 7 : Stage/alternance HARD exclusion (titre uniquement) ---
    HARD_TITLE_EXCLUDES = {"stage", "stagiaire", "alternance", "apprenti"}
    for kw in config.get("filters", {}).get("exclude_keywords", []):
        if kw.lower() in HARD_TITLE_EXCLUDES and kw.lower() in title_lower:
            score += scoring.get("stage_penalty", -50)
            break

    # --- Phase 8 : Freshness bonus ---
    score += _freshness_bonus(job.get("posted_date", ""))

    # --- Phase 9 : TF-IDF léger (similarité profil ↔ description, SANS LLM) ---
    score += _tfidf_similarity_bonus(profile, desc_lower)

    # --- Plafonnement ---
    job["fit_score"] = max(0, min(95, score))
    job["matched_skills"] = list(dict.fromkeys(matched))[:10]
    return job


def _tfidf_similarity_bonus(profile: Dict, desc_lower: str) -> int:
    """Calcule un bonus basé sur la similarité textuelle profil → description.

    Utilise un micro-TF-IDF : on extrait les termes clés du profil (headline +
    summary + target_keywords du profil actif) et on compte combien apparaissent
    dans la description. Pas de lib externe, juste du bag-of-words intelligent.
    """
    # Construire le "vocabulaire profil"
    pi = profile.get("personal_info", {})
    headline = (pi.get("headline_default") or "").lower()
    summary = (pi.get("summary_default") or "").lower()

    # Ajouter les target_keywords du profil actif (si spécifié)
    active_key = profile.get("_active_profile_key")
    profile_keywords = []
    if active_key:
        prof_def = (profile.get("profiles") or {}).get(active_key) or {}
        profile_keywords = [kw.lower() for kw in prof_def.get("target_keywords", [])]

    # Tokeniser le texte profil
    import re
    profile_text = f"{headline} {summary} {' '.join(profile_keywords)}"
    # Garder les tokens de 3+ caractères, supprimer les mots vides français
    STOP_WORDS = {
        "les", "des", "une", "par", "pour", "dans", "sur", "avec", "qui", "que",
        "est", "sont", "aux", "ses", "son", "leur", "cette", "ces", "tout",
        "tous", "elle", "ils", "plus", "pas", "mais", "bien", "très", "comme",
        "entre", "même", "fait", "été", "avoir", "être", "faire", "mise",
        "and", "the", "for", "with", "from", "that", "this", "also", "has",
    }
    profile_tokens = set()
    for token in re.findall(r"\b\w{3,}\b", profile_text):
        if token not in STOP_WORDS:
            profile_tokens.add(token)

    if not profile_tokens or not desc_lower:
        return 0

    # Compter les hits
    desc_tokens = set(re.findall(r"\b\w{3,}\b", desc_lower))
    matches = profile_tokens & desc_tokens
    ratio = len(matches) / len(profile_tokens) if profile_tokens else 0

    # Bonus progressif : 0-12 points
    if ratio >= 0.5:
        return 12
    elif ratio >= 0.35:
        return 9
    elif ratio >= 0.2:
        return 6
    elif ratio >= 0.1:
        return 3
    return 0


# ──────────────────────────────────────────────────────────────────
#  RE-RANKING IA (Gemini)
# ──────────────────────────────────────────────────────────────────

def llm_rerank_top(jobs: List[Dict], profile: Dict, top_n: int = 25) -> List[Dict]:
    if not jobs:
        return jobs
    candidates = sorted(jobs, key=lambda j: j.get("fit_score", 0), reverse=True)[:top_n]
    if not candidates:
        return jobs

    headline = profile.get("personal_info", {}).get("headline_default", "")
    summary = profile.get("personal_info", {}).get("summary_default", "")

    items = []
    for i, j in enumerate(candidates):
        desc = (j.get("description") or "")[:600]
        items.append(f"#{i}: {j.get('title','')} @ {j.get('company','')} — {j.get('location','')}\n{desc}")

    prompt = f"""Profil candidat :
HEADLINE: {headline}
RÉSUMÉ: {summary}

Évalue le fit de chacune des offres suivantes pour ce profil (0-100, raisonnement court).
Réponds UNIQUEMENT en JSON strict :
{{"scores": [{{"i": 0, "score": 85, "reason": "..."}}, ...]}}

Offres :
{chr(10).join(items)}
"""
    raw = _gemini_call(prompt, max_tokens=2000)
    if not raw:
        return jobs

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        data = json.loads(cleaned)
        scores = data.get("scores", [])
    except Exception:
        return jobs

    by_idx = {int(s.get("i", -1)): s for s in scores if isinstance(s, dict)}
    for i, job in enumerate(candidates):
        s = by_idx.get(i)
        if not s:
            continue
        ai = max(0, min(100, int(s.get("score", 0))))
        job["ai_score"] = ai
        job["ai_reason"] = (s.get("reason") or "").strip()[:240]
        heur = job.get("fit_score", 0)
        job["fit_score"] = int(round(0.6 * ai + 0.4 * heur))
    return jobs


# ──────────────────────────────────────────────────────────────────
#  EXTRACTION DES COMPÉTENCES (Gemini)
# ──────────────────────────────────────────────────────────────────

def llm_extract_skills(jobs: List[Dict], top_n: int = 15) -> List[Dict]:
    if not jobs:
        return jobs
    candidates = sorted(jobs, key=lambda j: j.get("fit_score", 0), reverse=True)[:top_n]
    for job in candidates:
        desc = (job.get("description") or "").strip()
        if len(desc) < 80:
            continue
        prompt = f"""Extrais les 5 à 10 compétences techniques clés requises par cette offre.
Renvoie UNIQUEMENT un JSON : {{"skills": ["...", "..."]}}.
Offre — {job.get('title','')} @ {job.get('company','')}
{desc[:1500]}"""
        raw = _gemini_call(prompt, max_tokens=300)
        if not raw:
            continue
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        try:
            data = json.loads(cleaned)
            skills = [s.strip() for s in data.get("skills", []) if isinstance(s, str) and s.strip()]
            job["extracted_skills"] = skills[:10]
        except Exception:
            continue
    return jobs
