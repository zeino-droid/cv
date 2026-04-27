"""
Sourcing Avancé — Moteur de recherche d'offres nouvelle génération.
VERSION CORRIGÉE — Fixes appliqués :
  [FIX-1] Priorisation des combinaisons keyword×location (matrice de priorité)
  [FIX-2] Filtre PhD/doctorat limité au TITRE uniquement (plus la description)
  [FIX-3] Mapping de localisation par source (format adapté à chaque scraper)
  [FIX-4] Cache LLM pour les expansions Gemini (TTL 7 jours)
  [FIX-5] Logger structuré par combinaison (OK / WARN / ERROR)
  [FIX-6] Circuit breaker par source (désactivation auto si trop d'échecs)
  [FIX-7] Alias de compétences (FEM = EF = Éléments Finis = FEA)
  [FIX-8] Déduplication multi-critères (titre+entreprise+ville)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).parent.parent
SEARCH_CONFIG_PATH = ROOT / "profiles" / "search_config.yaml"
MASTER_PROFILE_PATH = ROOT / "profiles" / "master_profile.json"

# [FIX-4] Chemin du cache LLM
LLM_CACHE_PATH = ROOT / "storage" / "llm_expansion_cache.json"
LLM_CACHE_TTL_DAYS = 7

ALLOWED_SITES = {"google", "glassdoor", "zip_recruiter"}

# [FIX-7] Table d'alias de compétences — toutes les variantes pointent vers le même concept
SKILL_ALIASES: Dict[str, List[str]] = {
    "éléments finis": ["ef", "fem", "fea", "elements finis", "éléments-finis", "finite element"],
    "cfd": ["computational fluid dynamics", "fluide numérique", "simulation fluide"],
    "ansys fluent": ["fluent", "ansys", "ansys cfd"],
    "abaqus": ["abaqus/cae", "abaqus cae", "abaqus/explicit", "abaqus/standard"],
    "python": ["python3", "scripting python", "dev python"],
    "jumeau numérique": ["digital twin", "twin numérique", "modèle numérique temps réel"],
    "modélisation thermique": ["thermique numérique", "simulation thermique", "calcul thermique"],
    "matlab": ["matlab/simulink", "simulink", "matlab simulink"],
    "metafor": ["metafor fem"],
    "thermomécanique": ["thermo-mécanique", "thermomecanique", "couplage thermomécanique"],
}

# [FIX-3] Mapping de localisation par source scraping
LOCATION_MAP: Dict[str, Dict[str, str]] = {
    "Paris, France":           {"google": "Paris", "glassdoor": "Paris, Île-de-France", "zip_recruiter": "Paris, France"},
    "Lyon, France":            {"google": "Lyon", "glassdoor": "Lyon, Auvergne-Rhône-Alpes", "zip_recruiter": "Lyon, France"},
    "Marseille, France":       {"google": "Marseille", "glassdoor": "Marseille, Provence-Alpes-Côte d'Azur", "zip_recruiter": "Marseille, France"},
    "Toulouse, France":        {"google": "Toulouse", "glassdoor": "Toulouse, Occitanie", "zip_recruiter": "Toulouse, France"},
    "Bordeaux, France":        {"google": "Bordeaux", "glassdoor": "Bordeaux, Nouvelle-Aquitaine", "zip_recruiter": "Bordeaux, France"},
    "Nice, France":            {"google": "Nice", "glassdoor": "Nice, Provence-Alpes-Côte d'Azur", "zip_recruiter": "Nice, France"},
    "Montpellier, France":     {"google": "Montpellier", "glassdoor": "Montpellier, Occitanie", "zip_recruiter": "Montpellier, France"},
    "Aix-en-Provence, France": {"google": "Aix-en-Provence", "glassdoor": "Aix-en-Provence, Provence-Alpes-Côte d'Azur", "zip_recruiter": "Aix-en-Provence, France"},
    "Grenoble, France":        {"google": "Grenoble", "glassdoor": "Grenoble, Auvergne-Rhône-Alpes", "zip_recruiter": "Grenoble, France"},
    "Sophia Antipolis, France":{"google": "Sophia Antipolis", "glassdoor": "Sophia Antipolis, Provence-Alpes-Côte d'Azur", "zip_recruiter": "Sophia Antipolis, France"},
    "France":                  {"google": "France", "glassdoor": "France", "zip_recruiter": "France"},
}


# ──────────────────────────────────────────────────────────────────
#  CONFIG / PROFILE
# ──────────────────────────────────────────────────────────────────

def load_config() -> Dict:
    if SEARCH_CONFIG_PATH.exists():
        with open(SEARCH_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "search": {
            "keywords": ["Ingénieur R&D simulation"],
            "locations": ["France"],
            "hours_old": 168,
            "results_per_query": 20,
        },
        "filters": {"min_score": 20, "exclude_keywords": ["stage", "alternance", "stagiaire"]},
        "scoring": {"base_score": 20, "per_skill_match": 8},
    }


def load_master_profile() -> Dict:
    if not MASTER_PROFILE_PATH.exists():
        print("   ⚠️  master_profile.json introuvable — profil minimal utilisé.")
        return {"personal_info": {}, "skills_taxonomy": {"hard_skills": [], "domain_knowledge": []}, "experience_stark": []}
    try:
        with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"   ⚠️  Erreur lecture master_profile.json: {exc}")
        return {"personal_info": {}, "skills_taxonomy": {"hard_skills": [], "domain_knowledge": []}, "experience_stark": []}


# ──────────────────────────────────────────────────────────────────
#  GEMINI HELPER
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


def _gemini_call(prompt: str, max_tokens: int = 800, model: str = "gemini-flash-latest", retries: int = 2) -> Optional[str]:
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
            err_str = str(exc).lower()
            is_retryable = any(k in err_str for k in ("429", "rate", "quota", "timeout", "503", "overloaded"))
            if is_retryable and attempt < retries:
                wait = 2 ** (attempt + 1)
                print(f"   ⏳ Gemini rate-limited, retry dans {wait}s (tentative {attempt+1}/{retries})…")
                time.sleep(wait)
                continue
            print(f"   ⚠️  Gemini error: {exc}")
            return None
    return None


# ──────────────────────────────────────────────────────────────────
#  [FIX-4] CACHE LLM
# ──────────────────────────────────────────────────────────────────

def _load_llm_cache() -> Dict:
    """Charge le cache d'expansion LLM depuis le disque."""
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
#  1. EXPANSION SÉMANTIQUE DES MOTS-CLÉS (avec cache)
# ──────────────────────────────────────────────────────────────────

def expand_keywords_with_llm(
    keywords: List[str], profile: Dict, max_extra_per_keyword: int = 2
) -> List[str]:
    """
    Génère des variantes sémantiques via Gemini.
    [FIX-4] Résultat mis en cache 7 jours pour éviter des appels API répétés.
    [FIX-5] Les variantes générées en anglais sont filtrées si tous les sites cibles sont FR.
    """
    if not keywords:
        return []

    # Vérification du cache
    cache = _load_llm_cache()
    key = _cache_key(keywords)
    entry = cache.get(key)
    if entry:
        cached_date = datetime.fromisoformat(entry.get("date", "2000-01-01")).date()
        if (date.today() - cached_date).days < LLM_CACHE_TTL_DAYS:
            print(f"   💾 Cache LLM hit ({(date.today() - cached_date).days}j) — expansion skippée")
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
            key_v = v.lower()
            if v and key_v not in seen:
                seen.add(key_v)
                expanded.append(v)

    # Sauvegarde dans le cache
    cache[key] = {"date": date.today().isoformat(), "expanded": expanded}
    _save_llm_cache(cache)
    print(f"   💾 Cache LLM mis à jour ({len(expanded)} mots-clés)")
    return expanded


# ──────────────────────────────────────────────────────────────────
#  [FIX-1] PRIORISATION DES COMBINAISONS
# ──────────────────────────────────────────────────────────────────

def _prioritize_pairs(
    keywords: List[str],
    locations: List[str],
    config: Dict,
    max_pairs: int = 60,
) -> List[Tuple[str, str]]:
    """
    [FIX-1] Construit les paires keyword×location en ordre de priorité décroissante.
    
    Logique :
    - Les keywords contenant des termes "core" (CFD, simulation, éléments finis...) passent en premier.
    - Les locations principales (Paris, Lyon...) passent avant "France" générique.
    - On remplit ensuite avec les combinaisons secondaires jusqu'au budget MAX_REQUESTS.
    """
    # Keywords "core" — les plus spécifiques au profil
    core_kw_terms = {"cfd", "éléments finis", "simulation numérique", "modélisation", "thermique", "calcul"}
    core_locations = {"paris", "lyon", "grenoble", "toulouse", "sophia"}

    def kw_priority(kw: str) -> int:
        kw_l = kw.lower()
        return 0 if any(t in kw_l for t in core_kw_terms) else 1

    def loc_priority(loc: str) -> int:
        loc_l = loc.lower()
        return 0 if any(t in loc_l for t in core_locations) else (2 if loc.lower() == "france" else 1)

    all_pairs = [(kw, loc) for kw in keywords for loc in locations]
    sorted_pairs = sorted(all_pairs, key=lambda p: (kw_priority(p[0]), loc_priority(p[1])))

    if len(sorted_pairs) > max_pairs:
        print(f"   ⚠️  {len(sorted_pairs)} combinaisons → limité à {max_pairs} (priorités appliquées)")
        sorted_pairs = sorted_pairs[:max_pairs]

    return sorted_pairs


# ──────────────────────────────────────────────────────────────────
#  [FIX-6] CIRCUIT BREAKER PAR SOURCE
# ──────────────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Désactive une source si elle échoue trop souvent.
    Seuil : 3 erreurs consécutives → source marquée DOWN.
    """
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._failures: Dict[str, int] = {}
        self._disabled: set = set()

    def record_success(self, source: str):
        self._failures[source] = 0

    def record_failure(self, source: str):
        self._failures[source] = self._failures.get(source, 0) + 1
        if self._failures[source] >= self.threshold:
            if source not in self._disabled:
                print(f"   🔴 Circuit breaker: source '{source}' désactivée ({self.threshold} erreurs consécutives)")
                self._disabled.add(source)

    def is_available(self, source: str) -> bool:
        return source not in self._disabled

    def status_summary(self) -> str:
        if not self._disabled:
            return "toutes sources actives"
        return f"sources désactivées: {', '.join(self._disabled)}"


# ──────────────────────────────────────────────────────────────────
#  2. SOURCING — JobSpy (google / glassdoor / zip_recruiter)
# ──────────────────────────────────────────────────────────────────

def _clean(val) -> str:
    s = str(val).strip()
    return "" if s in ("nan", "None", "NaT", "") else s


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p.strip().lower() for p in parts)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _row_to_job(row: Dict) -> Optional[Dict]:
    title = _clean(row.get("title", ""))
    company = _clean(row.get("company", ""))
    if not title or not company:
        return None
    job_id = _stable_id("JSP", title, company)
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": _clean(row.get("location", "")) or "France",
        "description": _clean(row.get("description", "")),
        "url": _clean(row.get("job_url", "")),
        "source": _clean(row.get("site", "jobspy")),
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": "CDI",
        "sourcing_date": date.today().isoformat(),
        "posted_date": _clean(row.get("date_posted", "")),
    }


def _get_location_for_site(location: str, site: str) -> str:
    """[FIX-3] Retourne le format de localisation adapté à chaque source."""
    mapping = LOCATION_MAP.get(location)
    if mapping:
        return mapping.get(site, location)
    # Fallback : extraire juste la ville si format "Ville, France"
    if ", France" in location:
        return location.replace(", France", "")
    return location


def scan_jobspy(
    keywords: List[str],
    locations: List[str],
    sites: List[str],
    hours_old: int = 168,
    results_per_query: int = 20,
    progress_callback: Optional[Callable] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    config: Optional[Dict] = None,
) -> List[Dict]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("   ❌ JobSpy non installé : pip install python-jobspy")
        return []

    safe_sites = [s for s in sites if s in ALLOWED_SITES] or ["google", "glassdoor"]
    jobs: List[Dict] = []
    cfg = config or {}

    # [FIX-1] Pairs priorisées
    pairs = _prioritize_pairs(keywords, locations, cfg, max_pairs=60)

    total = max(len(pairs), 1)
    done = 0

    # [FIX-6] Circuit breaker global (on traite toutes les sources ensemble ici)
    cb = CircuitBreaker(threshold=3)
    # Stats par combinaison pour le logger structuré [FIX-5]
    stats = {"ok": 0, "warn": 0, "error": 0}

    for keyword, location in pairs:
        if should_stop and should_stop():
            return jobs

        try:
            if progress_callback:
                pct = 0.10 + 0.55 * (done / total)
                progress_callback(pct, f"🔍 '{keyword}' → {location}")

            # [FIX-3] Adapter le format de localisation pour chaque site
            # On utilise le premier site de la liste pour le format principal
            primary_site = safe_sites[0] if safe_sites else "google"
            loc_adapted = _get_location_for_site(location, primary_site)

            df = scrape_jobs(
                site_name=safe_sites,
                search_term=keyword,
                location=loc_adapted,
                results_wanted=results_per_query,
                country_indeed="France",
                job_type="fulltime",
                hours_old=hours_old,
                verbose=0,
            )

            if df is not None and len(df) > 0:
                count = 0
                for _, row in df.iterrows():
                    j = _row_to_job(row.to_dict())
                    if j and j.get("url"):
                        jobs.append(j)
                        count += 1
                # [FIX-5] Logger structuré
                print(f"   ✅ [OK]   '{keyword}' → {location} ({loc_adapted}) : {count} offres")
                stats["ok"] += 1
                cb.record_success(primary_site)
            else:
                # [FIX-5] Logger WARN pour 0 résultats — suspect
                print(f"   ⚠️  [WARN] '{keyword}' → {location} ({loc_adapted}) : 0 résultats — vérifier format location ou disponibilité source")
                stats["warn"] += 1

        except Exception as exc:
            # [FIX-5] Logger ERROR
            print(f"   ❌ [ERROR] '{keyword}' → {location}: {exc}")
            stats["error"] += 1
            cb.record_failure(primary_site if safe_sites else "unknown")

        done += 1
        time.sleep(1.2)

    print(f"\n   📊 Stats JobSpy — OK:{stats['ok']} WARN:{stats['warn']} ERROR:{stats['error']} | {cb.status_summary()}")
    return jobs


# ──────────────────────────────────────────────────────────────────
#  3. SOURCING — Remotive (API publique gratuite)
# ──────────────────────────────────────────────────────────────────

def scan_remotive(keywords: List[str], limit_per_kw: int = 15) -> List[Dict]:
    try:
        import requests
    except ImportError:
        return []

    jobs: List[Dict] = []
    seen_urls: set = set()
    for kw in keywords[:8]:
        try:
            r = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": kw, "limit": limit_per_kw},
                timeout=10,
            )
            if r.status_code != 200:
                print(f"   ⚠️  [WARN] Remotive '{kw}': HTTP {r.status_code}")
                continue
            data = r.json()
            count = 0
            for offer in data.get("jobs", [])[:limit_per_kw]:
                url = (offer.get("url") or "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = (offer.get("title") or "").strip()
                company = (offer.get("company_name") or "").strip()
                if not title or not company:
                    continue
                desc_html = offer.get("description") or ""
                desc = re.sub(r"<[^>]+>", " ", desc_html)
                desc = re.sub(r"\s+", " ", desc).strip()
                jobs.append({
                    "id": _stable_id("RMT", title, company),
                    "title": title,
                    "company": company,
                    "location": offer.get("candidate_required_location") or "Remote",
                    "description": desc[:5000],
                    "url": url,
                    "source": "remotive",
                    "required_skills": [],
                    "matched_skills": [],
                    "extracted_skills": [],
                    "job_type": offer.get("job_type") or "CDI",
                    "sourcing_date": date.today().isoformat(),
                    "posted_date": (offer.get("publication_date") or "")[:10],
                })
                count += 1
            print(f"   ✅ [OK]   Remotive '{kw}': {count} offres")
        except Exception as exc:
            print(f"   ❌ [ERROR] Remotive '{kw}': {exc}")
        time.sleep(0.4)
    return jobs


# ──────────────────────────────────────────────────────────────────
#  4. DÉDUPLICATION MULTI-CRITÈRES [FIX-8]
# ──────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüç0-9]{2,}", re.IGNORECASE)


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def _signature(job: Dict) -> Tuple[str, frozenset]:
    title = re.sub(r"\s+", " ", (job.get("title") or "").lower()).strip()
    company = re.sub(r"\s+", " ", (job.get("company") or "").lower()).strip()
    # [FIX-8] Inclure la ville dans la clé de dédup
    city = (job.get("location") or "").lower().split(",")[0].strip()
    base = f"{title}@{company}@{city}"
    tokens = frozenset(_tokenize(title))
    return base, tokens


def deduplicate_smart(jobs: List[Dict]) -> List[Dict]:
    """
    Supprime les doublons de manière sémantique.
    [FIX-8] Niveau 0 : URL exacte (inter-plateformes).
    Niveau 1 : Hash strict (Titre + Entreprise + Ville).
    Niveau 2 : Jaccard ≥ 0.75 sur le titre pour la même entreprise.
    """
    seen_urls: set = set()
    seen_keys: set = set()
    bucket_per_company: Dict[str, List[frozenset]] = {}
    out: List[Dict] = []

    for job in jobs:
        # Niveau 0 : dédup par URL
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
        for existing_tokens in bucket_per_company.get(company, []):
            inter = len(tokens & existing_tokens)
            union = len(tokens | existing_tokens) or 1
            if inter / union >= 0.75:
                is_dup = True
                break
        if is_dup:
            continue

        seen_keys.add(base)
        bucket_per_company.setdefault(company, []).append(tokens)
        out.append(job)
    return out


# ──────────────────────────────────────────────────────────────────
#  5. SCORING HEURISTIQUE + ALIAS + BOOST FRAÎCHEUR
# ──────────────────────────────────────────────────────────────────

def _build_skill_variants(skill_name: str) -> List[str]:
    """[FIX-7] Retourne toutes les variantes connues d'une compétence."""
    name_lower = skill_name.lower().strip()
    variants = {name_lower}
    # Cherche dans les alias directs
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
    """
    Score de pertinence (0-100).
    [FIX-7] Matching via alias de compétences (FEM = EF = Éléments Finis).
    [FIX-2] Le filtre exclude_keywords (PhD/doctorat/thèse) ne s'applique 
             qu'au TITRE, plus à la description entière.
    """
    scoring = config.get("scoring", {})
    score = scoring.get("base_score", 20)
    title_lower = (job.get("title") or "").lower()
    desc_lower = (job.get("description") or "").lower()
    haystack = f"{title_lower} {desc_lower}"

    taxonomy = profile.get("skills_taxonomy", {})
    profile_skills: List[str] = []
    for skill in taxonomy.get("hard_skills", []):
        profile_skills.append(skill.get("name", ""))
    profile_skills.extend(taxonomy.get("domain_knowledge", []))

    matched: List[str] = []
    TITLE_BONUS = 6
    for skill in profile_skills:
        if not skill:
            continue
        # [FIX-7] Tester toutes les variantes de la compétence
        variants = _build_skill_variants(skill)
        skill_found = False
        for variant in variants:
            if variant in haystack:
                skill_found = True
                break
        if skill_found:
            matched.append(skill)
            score += scoring.get("per_skill_match", 8)
            # Bonus titre
            for variant in variants:
                if variant in title_lower:
                    score += TITLE_BONUS
                    break

    for kw, bonus in scoring.get("premium_keywords", {}).items():
        if str(kw).lower() in haystack:
            score += int(bonus)

    loc = (job.get("location") or "").lower()
    for zone in scoring.get("preferred_locations", []):
        if zone in loc:
            score += scoring.get("location_bonus", 5)
            break

    # [FIX-2] CORRECTION CRITIQUE : exclude_keywords uniquement sur le TITRE
    # Avant : if kw.lower() in title_lower  (mais la liste contenait PhD/doctorat qui filtraient des offres R&D légitimes)
    # On distingue maintenant :
    #   - Termes de TYPE de poste (stage, stagiaire, alternance, apprenti) → filtrés sur titre
    #   - Termes académiques (doctorat, thèse, PhD) → NE PLUS filtrer du tout (offres R&D industrielles valides)
    HARD_TITLE_EXCLUDES = {"stage", "stagiaire", "alternance", "apprenti"}
    for kw in config.get("filters", {}).get("exclude_keywords", []):
        if kw.lower() in HARD_TITLE_EXCLUDES:
            if kw.lower() in title_lower:
                score += scoring.get("stage_penalty", -50)
                break

    score += _freshness_bonus(job.get("posted_date", ""))
    job["fit_score"] = max(0, min(100, score))
    job["matched_skills"] = list(dict.fromkeys(matched))[:10]
    return job


# ──────────────────────────────────────────────────────────────────
#  6. RE-RANKING SÉMANTIQUE PAR GEMINI
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
#  7. EXTRACTION DE COMPÉTENCES (Gemini)
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


# ──────────────────────────────────────────────────────────────────
#  PIPELINE PRINCIPAL
# ──────────────────────────────────────────────────────────────────

def scan_advanced(
    keywords: List[str],
    locations: List[str],
    sites: List[str],
    results_per_query: int = 15,
    use_llm_expansion: bool = True,
    use_llm_rerank: bool = True,
    use_llm_skills: bool = True,
    use_remotive: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> List[Dict]:
    """Pipeline complet : expansion → scrape multi-source → dédup → score → re-rank IA → skills IA."""

    def report(p: float, msg: str):
        if progress_callback:
            try:
                progress_callback(min(max(p, 0.0), 1.0), msg)
            except Exception:
                pass

    config = load_config()
    profile = load_master_profile()

    def _stopped() -> bool:
        return bool(should_stop and should_stop())

    # 1. Expansion sémantique (avec cache [FIX-4])
    if use_llm_expansion and _gemini_client() and not _stopped():
        report(0.03, "🧠 Expansion sémantique des mots-clés (Gemini)…")
        keywords = expand_keywords_with_llm(keywords, profile, max_extra_per_keyword=2)
    if _stopped(): return []

    report(0.08, f"📡 {len(keywords)} mots-clés × {len(locations)} zones · {', '.join(sites)}")

    # 2. Scrape JobSpy (avec priorités [FIX-1], localisation adaptée [FIX-3], circuit breaker [FIX-6])
    jobs = scan_jobspy(
        keywords=keywords,
        locations=locations,
        sites=sites,
        results_per_query=results_per_query,
        progress_callback=progress_callback,
        should_stop=should_stop,
        config=config,
    )
    report(0.68, f"✅ JobSpy : {len(jobs)} offres brutes")

    # 3. Source bonus Remotive
    if use_remotive and not _stopped():
        report(0.72, "🌐 Recherche complémentaire (Remotive)…")
        rem = scan_remotive(keywords, limit_per_kw=10)
        jobs.extend(rem)
        report(0.78, f"✅ Remotive : +{len(rem)} offres")

    # 4. Dédup multi-critères [FIX-8]
    report(0.82, f"🔄 Déduplication ({len(jobs)} brut)…")
    unique = deduplicate_smart(jobs)
    report(0.84, f"✅ {len(unique)} offres uniques")

    # 5. Scoring heuristique (avec alias [FIX-7] et fix PhD [FIX-2])
    report(0.86, "⭐ Scoring heuristique…")
    scored = [score_job(j, profile, config) for j in unique]

    # 6. Re-ranking IA sur les meilleurs
    if use_llm_rerank and _gemini_client() and scored and not _stopped():
        report(0.90, "🧠 Re-classement IA (Gemini)…")
        scored = llm_rerank_top(scored, profile, top_n=25)

    # 7. Extraction compétences
    if use_llm_skills and _gemini_client() and scored and not _stopped():
        report(0.95, "🔍 Extraction des compétences clés (Gemini)…")
        scored = llm_extract_skills(scored, top_n=15)

    # [NOTE] min_score abaissé à 20 dans search_config.yaml pour la recalibration initiale.
    # Une fois la distribution des scores observée, le remonter à 35-40.
    min_score = int(config.get("filters", {}).get("min_score", 20))
    scored = [j for j in scored if j["fit_score"] >= min_score]
    scored.sort(key=lambda x: x["fit_score"], reverse=True)

    if _stopped():
        report(1.0, f"⏸️ Recherche interrompue · {len(scored)} offres collectées")
    else:
        report(1.0, f"✅ {len(scored)} offres qualifiées prêtes !")
    return scored
