"""
Sourcing Avancé — Moteur de recherche d'offres nouvelle génération.

Innovations vs. JobSpy seul :
  1. EXPANSION SÉMANTIQUE des mots-clés via Gemini (génère des variantes pertinentes)
  2. SOURCES MULTIPLES sans LinkedIn / Indeed (Google Jobs, Glassdoor, ZipRecruiter, Remotive)
  3. DÉDUPLICATION TF-IDF (détecte les quasi-doublons entre sources)
  4. RE-RANKING IA des top candidats par Gemini (score de fit profond + raisonnement)
  5. EXTRACTION DE COMPÉTENCES depuis les descriptions par Gemini
  6. BOOST DE FRAÎCHEUR (offres récentes prioritaires)
"""

from __future__ import annotations

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

ALLOWED_SITES = {"google", "glassdoor", "zip_recruiter"}


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
        "filters": {"min_score": 40, "exclude_keywords": ["stage", "alternance", "stagiaire"]},
        "scoring": {"base_score": 20, "per_skill_match": 8},
    }


def load_master_profile() -> Dict:
    with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
#  GEMINI HELPER
# ──────────────────────────────────────────────────────────────────

def _gemini_client():
    """Retourne un client Gemini ou None si la clé n'est pas dispo."""
    try:
        from google import genai
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return None
        return genai.Client(api_key=key)
    except Exception:
        return None


def _gemini_call(prompt: str, max_tokens: int = 800, model: str = "gemini-flash-latest") -> Optional[str]:
    client = _gemini_client()
    if client is None:
        return None
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
        print(f"   ⚠️  Gemini error: {exc}")
        return None


# ──────────────────────────────────────────────────────────────────
#  1. EXPANSION SÉMANTIQUE DES MOTS-CLÉS
# ──────────────────────────────────────────────────────────────────

def expand_keywords_with_llm(
    keywords: List[str], profile: Dict, max_extra_per_keyword: int = 2
) -> List[str]:
    """
    Demande à Gemini de générer des variantes sémantiques de chaque mot-clé,
    adaptées au profil candidat. Renvoie la liste enrichie (originaux + variantes).
    """
    if not keywords:
        return []

    domain = profile.get("personal_info", {}).get("headline_default", "")
    summary = profile.get("personal_info", {}).get("summary_default", "")

    prompt = f"""Tu es un recruteur expert. Voici un profil candidat :
HEADLINE: {domain}
RÉSUMÉ: {summary}

Voici ses mots-clés de recherche actuels :
{chr(10).join(f"- {k}" for k in keywords)}

Génère pour CHAQUE mot-clé jusqu'à {max_extra_per_keyword} variantes sémantiques pertinentes
(synonymes, intitulés équivalents, formulations alternatives utilisées par les recruteurs français).
Réponds UNIQUEMENT au format JSON strict : {{"keyword_original": ["variante1", "variante2"]}}.
Pas de texte autour, pas de markdown.
"""
    raw = _gemini_call(prompt, max_tokens=1200)
    if not raw:
        return list(keywords)

    # Nettoie un éventuel ```json ... ``` autour
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
            key = v.lower()
            if v and key not in seen:
                seen.add(key)
                expanded.append(v)
    return expanded


# ──────────────────────────────────────────────────────────────────
#  2. SOURCING — JobSpy (google / glassdoor / zip_recruiter)
# ──────────────────────────────────────────────────────────────────

def _clean(val) -> str:
    s = str(val).strip()
    return "" if s in ("nan", "None", "NaT", "") else s


def _row_to_job(row: Dict) -> Optional[Dict]:
    title = _clean(row.get("title", ""))
    company = _clean(row.get("company", ""))
    if not title or not company:
        return None
    job_id = f"JSP-{abs(hash(title + company))}"
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


def scan_jobspy(
    keywords: List[str],
    locations: List[str],
    sites: List[str],
    hours_old: int = 168,
    results_per_query: int = 20,
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("   ❌ JobSpy non installé : pip install python-jobspy")
        return []

    safe_sites = [s for s in sites if s in ALLOWED_SITES] or ["google", "glassdoor"]
    jobs: List[Dict] = []
    total = max(len(keywords) * len(locations), 1)
    done = 0

    for keyword in keywords:
        for location in locations:
            try:
                if progress_callback:
                    pct = 0.10 + 0.55 * (done / total)
                    progress_callback(pct, f"🔍 '{keyword}' → {location}")

                df = scrape_jobs(
                    site_name=safe_sites,
                    search_term=keyword,
                    location=location,
                    results_wanted=results_per_query,
                    country_indeed="France",
                    job_type="fulltime",
                    hours_old=hours_old,
                    verbose=0,
                )
                if df is not None and len(df) > 0:
                    for _, row in df.iterrows():
                        j = _row_to_job(row.to_dict())
                        if j and j.get("url"):
                            jobs.append(j)
            except Exception as exc:
                print(f"   ⚠️  JobSpy '{keyword}' → {location}: {exc}")
            done += 1
            time.sleep(1.2)
    return jobs


# ──────────────────────────────────────────────────────────────────
#  3. SOURCING — Remotive (API publique gratuite, sans clé)
# ──────────────────────────────────────────────────────────────────

def scan_remotive(keywords: List[str], limit_per_kw: int = 15) -> List[Dict]:
    """Source bonus : Remotive (offres tech, beaucoup de remote ouvert à la France)."""
    try:
        import requests
    except ImportError:
        return []

    jobs: List[Dict] = []
    seen_urls: set = set()
    for kw in keywords[:8]:  # limite pour ne pas spammer l'API
        try:
            r = requests.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": kw, "limit": limit_per_kw},
                timeout=10,
            )
            if r.status_code != 200:
                continue
            data = r.json()
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
                    "id": f"RMT-{abs(hash(title + company))}",
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
        except Exception as exc:
            print(f"   ⚠️  Remotive '{kw}': {exc}")
        time.sleep(0.4)
    return jobs


# ──────────────────────────────────────────────────────────────────
#  4. DÉDUPLICATION TF-IDF (sémantique légère)
# ──────────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüç0-9]{3,}", re.IGNORECASE)


def _tokenize(text: str) -> List[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text or "")]


def _signature(job: Dict) -> Tuple[str, frozenset]:
    """Signature normalisée + ensemble de tokens significatifs du titre."""
    title = re.sub(r"\s+", " ", (job.get("title") or "").lower()).strip()
    company = re.sub(r"\s+", " ", (job.get("company") or "").lower()).strip()
    base = f"{title}@{company}"
    tokens = frozenset(_tokenize(title))
    return base, tokens


def deduplicate_smart(jobs: List[Dict]) -> List[Dict]:
    """Déduplication 2 niveaux : exact (titre+entreprise) + Jaccard sur titre (≥0.75)."""
    seen_keys: set = set()
    bucket_per_company: Dict[str, List[frozenset]] = {}
    out: List[Dict] = []

    for job in jobs:
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
#  5. SCORING HEURISTIQUE + BOOST FRAÎCHEUR
# ──────────────────────────────────────────────────────────────────

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
    scoring = config.get("scoring", {})
    score = scoring.get("base_score", 20)
    haystack = f"{job.get('title','')} {job.get('description','')}".lower()

    taxonomy = profile.get("skills_taxonomy", {})
    profile_skills: List[str] = []
    for skill in taxonomy.get("hard_skills", []):
        profile_skills.append(skill.get("name", ""))
    profile_skills.extend(taxonomy.get("domain_knowledge", []))

    matched: List[str] = []
    for skill in profile_skills:
        if not skill:
            continue
        if skill.lower() in haystack:
            matched.append(skill)
            score += scoring.get("per_skill_match", 8)

    for kw, bonus in scoring.get("premium_keywords", {}).items():
        if str(kw).lower() in haystack:
            score += int(bonus)

    loc = (job.get("location") or "").lower()
    for zone in scoring.get("preferred_locations", []):
        if zone in loc:
            score += scoring.get("location_bonus", 5)
            break

    title_lower = (job.get("title") or "").lower()
    for kw in config.get("filters", {}).get("exclude_keywords", []):
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
    """
    Demande à Gemini de re-scorer les top N offres avec un score de fit profond.
    Stocke `ai_score` (0-100) et `ai_reason` (1 phrase) sur chaque offre.
    Le `fit_score` final devient une moyenne pondérée 60% IA + 40% heuristique.
    """
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
    """Extrait les vraies compétences requises depuis les descriptions des top offres."""
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

    # 1. Expansion sémantique
    if use_llm_expansion and _gemini_client():
        report(0.03, "🧠 Expansion sémantique des mots-clés (Gemini)…")
        keywords = expand_keywords_with_llm(keywords, profile, max_extra_per_keyword=2)

    report(0.08, f"📡 {len(keywords)} requêtes × {len(locations)} zones · {', '.join(sites)}")

    # 2. Scrape JobSpy
    jobs = scan_jobspy(
        keywords=keywords,
        locations=locations,
        sites=sites,
        results_per_query=results_per_query,
        progress_callback=progress_callback,
    )
    report(0.68, f"✅ JobSpy : {len(jobs)} offres brutes")

    # 3. Source bonus Remotive
    if use_remotive:
        report(0.72, "🌐 Recherche complémentaire (Remotive)…")
        rem = scan_remotive(keywords, limit_per_kw=10)
        jobs.extend(rem)
        report(0.78, f"✅ Remotive : +{len(rem)} offres")

    # 4. Dédup intelligente
    report(0.82, f"🔄 Déduplication sémantique ({len(jobs)} brut)…")
    unique = deduplicate_smart(jobs)
    report(0.84, f"✅ {len(unique)} offres uniques")

    # 5. Scoring heuristique
    report(0.86, "⭐ Scoring heuristique…")
    scored = [score_job(j, profile, config) for j in unique]

    # 6. Re-ranking IA sur les meilleurs
    if use_llm_rerank and _gemini_client() and scored:
        report(0.90, "🧠 Re-classement IA des meilleurs candidats (Gemini)…")
        scored = llm_rerank_top(scored, profile, top_n=25)

    # 7. Extraction compétences
    if use_llm_skills and _gemini_client() and scored:
        report(0.95, "🔍 Extraction des compétences clés (Gemini)…")
        scored = llm_extract_skills(scored, top_n=15)

    min_score = int(config.get("filters", {}).get("min_score", 40))
    scored = [j for j in scored if j["fit_score"] >= min_score]
    scored.sort(key=lambda x: x["fit_score"], reverse=True)
    report(1.0, f"✅ {len(scored)} offres qualifiées prêtes !")
    return scored
