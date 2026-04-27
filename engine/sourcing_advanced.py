"""
Sourcing Avancé — Moteur de recherche d'offres nouvelle génération.

VERSION CORRIGÉE — Fixes appliqués :
  [FIX-1]  Priorisation des combinaisons keyword × location (matrice de priorité)
  [FIX-2]  Filtre PhD/doctorat limité au TITRE uniquement (plus la description)
  [FIX-3]  Mapping de localisation par source (format adapté à chaque scraper)
  [FIX-4]  Cache LLM pour les expansions Gemini (TTL 7 jours)
  [FIX-5]  Logger structuré par combinaison (OK / WARN / ERROR)
  [FIX-6]  Circuit breaker par source (désactivation auto si trop d'échecs)
  [FIX-7]  Alias de compétences (FEM = EF = Éléments Finis = FEA)
  [FIX-8]  Déduplication multi-critères (titre + entreprise + ville)

NOUVEAUX FIXES (vraies causes du « 0 résultats ») :
  [FIX-9]  Utilisation de `google_search_term` natif JobSpy (sans ça Google Jobs
           renvoie ~0 sur des requêtes FR techniques).
  [FIX-10] Suppression de ZipRecruiter (US/CA only — renvoyait toujours 0 pour la France)
           et ajout d'Indeed (indeed.fr est la 1ère source d'offres CDI en France).
  [FIX-11] Itération SITE PAR SITE dans scrape_jobs : un appel multi-source masquait
           les échecs partiels et empêchait le circuit breaker de fonctionner.
  [FIX-12] Défauts moins restrictifs : `hours_old` 720h (30 j) au lieu de 168 (7 j),
           `job_type=None` (beaucoup d'offres CDI n'ont pas de métadonnée job_type ;
           le filtre les éliminait silencieusement).
  [FIX-13] `country_indeed="france"` (minuscules — canonical pour Indeed et Glassdoor).
  [FIX-14] Fallback : si AUCUNE offre ne passe `min_score`, on garde les 25 meilleures
           plutôt que de renvoyer une liste vide.
  [FIX-15] Diagnostic final : si 0 offres brutes après tous les sites, on émet un
           message clair pour l'utilisateur (clé Gemini absente, sources HS, etc.).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).parent.parent
SEARCH_CONFIG_PATH = ROOT / "profiles" / "search_config.yaml"
MASTER_PROFILE_PATH = ROOT / "profiles" / "master_profile.json"

LLM_CACHE_PATH = ROOT / "storage" / "llm_expansion_cache.json"
LLM_CACHE_TTL_DAYS = 7

# [FIX-10] ZipRecruiter retiré (US/CA only). Indeed ajouté (1ʳᵉ source FR).
ALLOWED_SITES = {"google", "glassdoor", "indeed", "linkedin"}

# [FIX-7] Alias de compétences — toutes les variantes pointent vers le même concept
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
    "Paris, France":           {"google": "Paris, France",        "glassdoor": "Paris, Île-de-France",                      "indeed": "Paris (75)",            "linkedin": "Paris, France"},
    "Lyon, France":            {"google": "Lyon, France",         "glassdoor": "Lyon, Auvergne-Rhône-Alpes",                "indeed": "Lyon (69)",             "linkedin": "Lyon, France"},
    "Marseille, France":       {"google": "Marseille, France",    "glassdoor": "Marseille, Provence-Alpes-Côte d'Azur",     "indeed": "Marseille (13)",        "linkedin": "Marseille, France"},
    "Toulouse, France":        {"google": "Toulouse, France",     "glassdoor": "Toulouse, Occitanie",                       "indeed": "Toulouse (31)",         "linkedin": "Toulouse, France"},
    "Bordeaux, France":        {"google": "Bordeaux, France",     "glassdoor": "Bordeaux, Nouvelle-Aquitaine",              "indeed": "Bordeaux (33)",         "linkedin": "Bordeaux, France"},
    "Nice, France":            {"google": "Nice, France",         "glassdoor": "Nice, Provence-Alpes-Côte d'Azur",          "indeed": "Nice (06)",             "linkedin": "Nice, France"},
    "Montpellier, France":     {"google": "Montpellier, France",  "glassdoor": "Montpellier, Occitanie",                    "indeed": "Montpellier (34)",      "linkedin": "Montpellier, France"},
    "Aix-en-Provence, France": {"google": "Aix-en-Provence, France", "glassdoor": "Aix-en-Provence, Provence-Alpes-Côte d'Azur", "indeed": "Aix-en-Provence (13)", "linkedin": "Aix-en-Provence, France"},
    "Grenoble, France":        {"google": "Grenoble, France",     "glassdoor": "Grenoble, Auvergne-Rhône-Alpes",            "indeed": "Grenoble (38)",         "linkedin": "Grenoble, France"},
    "Sophia Antipolis, France":{"google": "Sophia Antipolis, France", "glassdoor": "Sophia Antipolis, Provence-Alpes-Côte d'Azur", "indeed": "Sophia Antipolis (06)", "linkedin": "Sophia Antipolis, France"},
    "France":                  {"google": "France",               "glassdoor": "France",                                    "indeed": "France",                "linkedin": "France"},
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
            "hours_old": 720,
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
    """[FIX-4] Résultat mis en cache 7 jours pour éviter des appels API répétés."""
    if not keywords:
        return []

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
    """[FIX-1] Construit les paires keyword × location en ordre de priorité décroissante."""
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
    """Désactive une source après N échecs consécutifs."""
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._failures: Dict[str, int] = {}
        self._disabled: set = set()

    def record_success(self, source: str):
        self._failures[source] = 0

    def record_failure(self, source: str):
        self._failures[source] = self._failures.get(source, 0) + 1
        if self._failures[source] >= self.threshold and source not in self._disabled:
            print(f"   🔴 Circuit breaker: source '{source}' désactivée ({self.threshold} erreurs consécutives)")
            self._disabled.add(source)

    def is_available(self, source: str) -> bool:
        return source not in self._disabled

    def status_summary(self) -> str:
        if not self._disabled:
            return "toutes sources actives"
        return f"sources désactivées: {', '.join(self._disabled)}"


# ──────────────────────────────────────────────────────────────────
#  2. SOURCING — JobSpy (google / glassdoor / indeed / linkedin)
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
    if ", France" in location and site in ("google", "linkedin"):
        return location
    if ", France" in location:
        return location.replace(", France", "")
    return location


def _build_google_search_term(keyword: str, location_human: str, hours_old: int) -> str:
    """
    [FIX-9] Construit le `google_search_term` natif de Google Jobs.
    Sans ce paramètre, le scraper Google de JobSpy renvoie ~0 résultats sur des
    requêtes FR techniques. Format recommandé par la doc JobSpy.
    """
    days = max(1, int(round(hours_old / 24)))
    return f'"{keyword}" jobs near {location_human} since {days} days ago'


def scan_jobspy(
    keywords: List[str],
    locations: List[str],
    sites: List[str],
    hours_old: int = 720,
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

    safe_sites = [s for s in sites if s in ALLOWED_SITES] or ["google", "indeed"]
    jobs: List[Dict] = []
    cfg = config or {}

    pairs = _prioritize_pairs(keywords, locations, cfg, max_pairs=60)
    total = max(len(pairs) * len(safe_sites), 1)
    done = 0

    cb = CircuitBreaker(threshold=3)
    stats = {"ok": 0, "warn": 0, "error": 0}

    for keyword, location in pairs:
        if should_stop and should_stop():
            return jobs

        # [FIX-11] Itère SITE PAR SITE — un seul appel multi-source masquait
        # les échecs partiels et faussait le circuit breaker.
        for site in safe_sites:
            if should_stop and should_stop():
                return jobs

            # [FIX-13] Skip si la source a été désactivée par le circuit breaker
            if not cb.is_available(site):
                done += 1
                continue

            try:
                if progress_callback:
                    pct = 0.10 + 0.55 * (done / total)
                    progress_callback(pct, f"🔍 [{site}] '{keyword}' → {location}")

                loc_adapted = _get_location_for_site(location, site)

                # [FIX-9] google_search_term natif pour Google Jobs
                kwargs = dict(
                    site_name=[site],
                    search_term=keyword,
                    location=loc_adapted,
                    results_wanted=results_per_query,
                    country_indeed="france",  # [FIX-13] minuscules canonical
                    hours_old=hours_old,
                    verbose=0,
                )
                if site == "google":
                    kwargs["google_search_term"] = _build_google_search_term(
                        keyword, loc_adapted, hours_old
                    )
                # [FIX-12] On NE force plus job_type="fulltime" : beaucoup d'offres
                # CDI n'ont pas de métadonnée job_type et étaient éliminées.

                df = scrape_jobs(**kwargs)

                if df is not None and len(df) > 0:
                    count = 0
                    for _, row in df.iterrows():
                        j = _row_to_job(row.to_dict())
                        if j and j.get("url"):
                            jobs.append(j)
                            count += 1
                    print(f"   ✅ [OK]   [{site}] '{keyword}' → {loc_adapted} : {count} offres")
                    stats["ok"] += 1
                    cb.record_success(site)
                else:
                    print(f"   ⚠️  [WARN] [{site}] '{keyword}' → {loc_adapted} : 0 résultats")
                    stats["warn"] += 1

            except Exception as exc:
                print(f"   ❌ [ERROR] [{site}] '{keyword}' → {location}: {exc}")
                stats["error"] += 1
                cb.record_failure(site)

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
    city = (job.get("location") or "").lower().split(",")[0].strip()
    base = f"{title}@{company}@{city}"
    tokens = frozenset(_tokenize(title))
    return base, tokens


def deduplicate_smart(jobs: List[Dict]) -> List[Dict]:
    """
    [FIX-8] Dédup multi-niveaux :
      Niveau 0 : URL exacte (inter-plateformes).
      Niveau 1 : Hash strict (Titre + Entreprise + Ville).
      Niveau 2 : Jaccard ≥ 0.75 sur le titre pour la même entreprise.
    """
    seen_urls: set = set()
    seen_keys: set = set()
    bucket_per_company: Dict[str, List[frozenset]] = {}
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
    [FIX-7] Matching via alias de compétences (FEM = EF = Éléments Finis).
    [FIX-2] Le filtre exclude_keywords ne s'applique qu'au TITRE et uniquement
            sur les termes de TYPE de poste (stage, alternance...). PhD/doctorat
            retirés (offres R&D industrielles légitimes).
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
        variants = _build_skill_variants(skill)
        skill_found = False
        for variant in variants:
            if variant in haystack:
                skill_found = True
                break
        if skill_found:
            matched.append(skill)
            score += scoring.get("per_skill_match", 8)
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

    # [FIX-2] Filtre uniquement sur le TITRE et uniquement sur des types de poste
    HARD_TITLE_EXCLUDES = {"stage", "stagiaire", "alternance", "apprenti"}
    for kw in config.get("filters", {}).get("exclude_keywords", []):
        if kw.lower() in HARD_TITLE_EXCLUDES and kw.lower() in title_lower:
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
    results_per_query: int = 20,
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

    # [FIX-12] hours_old plus permissif (30 j par défaut au lieu de 7 j)
    hours_old = int(config.get("search", {}).get("hours_old", 720))

    def _stopped() -> bool:
        return bool(should_stop and should_stop())

    if use_llm_expansion and _gemini_client() and not _stopped():
        report(0.03, "🧠 Expansion sémantique des mots-clés (Gemini)…")
        keywords = expand_keywords_with_llm(keywords, profile, max_extra_per_keyword=2)
    if _stopped(): return []

    report(0.08, f"📡 {len(keywords)} mots-clés × {len(locations)} zones · {', '.join(sites)}")

    jobs = scan_jobspy(
        keywords=keywords,
        locations=locations,
        sites=sites,
        hours_old=hours_old,
        results_per_query=results_per_query,
        progress_callback=progress_callback,
        should_stop=should_stop,
        config=config,
    )
    report(0.68, f"✅ JobSpy : {len(jobs)} offres brutes")

    if use_remotive and not _stopped():
        report(0.72, "🌐 Recherche complémentaire (Remotive)…")
        rem = scan_remotive(keywords, limit_per_kw=10)
        jobs.extend(rem)
        report(0.78, f"✅ Remotive : +{len(rem)} offres")

    # [FIX-15] Diagnostic final si 0 offres brutes
    if not jobs:
        report(0.82, "❌ 0 offre brute collectée — vérifiez : sites disponibles, "
                     "format des localisations, ou présence de la clé GEMINI_API_KEY.")
        return []

    report(0.82, f"🔄 Déduplication ({len(jobs)} brut)…")
    unique = deduplicate_smart(jobs)
    report(0.84, f"✅ {len(unique)} offres uniques")

    report(0.86, "⭐ Scoring heuristique…")
    scored = [score_job(j, profile, config) for j in unique]

    if use_llm_rerank and _gemini_client() and scored and not _stopped():
        report(0.90, "🧠 Re-classement IA (Gemini)…")
        scored = llm_rerank_top(scored, profile, top_n=25)

    if use_llm_skills and _gemini_client() and scored and not _stopped():
        report(0.95, "🔍 Extraction des compétences clés (Gemini)…")
        scored = llm_extract_skills(scored, top_n=15)

    min_score = int(config.get("filters", {}).get("min_score", 20))
    qualified = [j for j in scored if j["fit_score"] >= min_score]

    # [FIX-14] Fallback : si AUCUNE offre ne passe le seuil, on garde les 25 meilleures
    if not qualified and scored:
        print(f"   ⚠️  Aucune offre n'atteint min_score={min_score} — fallback sur les 25 meilleures.")
        qualified = sorted(scored, key=lambda x: x["fit_score"], reverse=True)[:25]

    qualified.sort(key=lambda x: x["fit_score"], reverse=True)

    if _stopped():
        report(1.0, f"⏸️ Recherche interrompue · {len(qualified)} offres collectées")
    else:
        report(1.0, f"✅ {len(qualified)} offres qualifiées prêtes !")
    return qualified
