"""
Sourcing via JobSpy — LinkedIn + Indeed + Google Jobs France
Remplace l'IndeedFranceScraper cassé de mega_sourcing.py
"""

import json
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import yaml

ROOT = Path(__file__).parent.parent
SEARCH_CONFIG_PATH = ROOT / "profiles" / "search_config.yaml"
MASTER_PROFILE_PATH = ROOT / "profiles" / "master_profile.json"


def load_config() -> Dict:
    if not SEARCH_CONFIG_PATH.exists():
        return {
            "search": {
                "keywords": ["Ingénieur R&D simulation"],
                "locations": ["France"],
                "hours_old": 168,
                "results_per_query": 20,
            },
            "filters": {
                "min_score": 40,
                "exclude_keywords": ["stage", "alternance", "stagiaire"],
            },
            "scoring": {
                "base_score": 20,
                "per_skill_match": 8,
                "premium_keywords": {
                    "simulation": 5,
                    "thermique": 4,
                    "CFD": 5,
                    "Python": 4,
                    "Abaqus": 6,
                    "Ansys": 5,
                },
                "preferred_locations": [
                    "paris", "lyon", "marseille", "toulouse", "bordeaux", "nice", "montpellier", "grenoble",
                ],
                "location_bonus": 5,
                "stage_penalty": -50,
            },
        }
    with open(SEARCH_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_master_profile() -> Dict:
    with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def score_job(job: Dict, profile: Dict, config: Dict) -> Dict:
    """Score une offre par rapport au profil candidat."""
    scoring = config.get("scoring", {})
    score = scoring.get("base_score", 20)
    haystack = f"{job.get('title', '')} {job.get('description', '')}".lower()

    # Match compétences du profil (New Schema: skills_taxonomy)
    taxonomy = profile.get("skills_taxonomy", {})
    profile_skills: List[str] = []
    
    # Hard skills
    for skill in taxonomy.get("hard_skills", []):
        profile_skills.append(skill.get("name", ""))
    
    # Domain knowledge
    profile_skills.extend(taxonomy.get("domain_knowledge", []))

    matched: List[str] = []
    for skill in profile_skills:
        if not skill: continue
        if skill.lower() in haystack:
            matched.append(skill)
            score += scoring.get("per_skill_match", 8)

    # Mots-clés premium
    for kw, bonus in scoring.get("premium_keywords", {}).items():
        if str(kw).lower() in haystack:
            score += int(bonus)

    # Bonus localisation préférée
    loc = job.get("location", "").lower()
    for zone in scoring.get("preferred_locations", []):
        if zone in loc:
            score += scoring.get("location_bonus", 5)
            break

    # Pénalité stage/alternance
    title_lower = job.get("title", "").lower()
    for kw in config.get("filters", {}).get("exclude_keywords", []):
        if kw.lower() in title_lower:
            score += scoring.get("stage_penalty", -50)
            break

    job["fit_score"] = max(0, min(100, score))
    job["matched_skills"] = list(dict.fromkeys(matched))[:10]
    return job


def _clean(val) -> str:
    """Nettoie une valeur pandas (gère NaN, None, etc.)."""
    s = str(val).strip()
    return "" if s in ("nan", "None", "NaT", "") else s


def jobspy_to_standard(df_row: Dict) -> Optional[Dict]:
    """Convertit une ligne JobSpy DataFrame en format standard."""
    try:
        title = _clean(df_row.get("title", ""))
        company = _clean(df_row.get("company", ""))
        if not title or not company:
            return None

        job_id = f"JSP-{abs(hash(title + company))}"
        location = _clean(df_row.get("location", "")) or "France"
        url = _clean(df_row.get("job_url", ""))
        description = _clean(df_row.get("description", ""))
        source = _clean(df_row.get("site", "jobspy"))

        return {
            "id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "url": url,
            "required_skills": [],
            "matched_skills": [],
            "source": source,
            "job_type": "CDI",
            "sourcing_date": date.today().isoformat(),
        }
    except Exception:
        return None


def scan_with_jobspy(
    keywords: List[str],
    locations: List[str],
    hours_old: int = 168,
    results_per_query: int = 20,
    progress_callback: Optional[Callable] = None,
) -> List[Dict]:
    """
    Scan LinkedIn + Indeed + Google Jobs via JobSpy.
    Retourne une liste de jobs normalisés.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        print("   ❌ JobSpy non installé : pip install python-jobspy")
        return []

    all_jobs: List[Dict] = []
    total = max(len(keywords) * len(locations), 1)
    done = 0

    for keyword in keywords:
        for location in locations:
            try:
                if progress_callback:
                    pct = 0.05 + 0.78 * (done / total)
                    progress_callback(pct, f"🔍 '{keyword}' → {location}")

                df = scrape_jobs(
                    site_name=["linkedin", "indeed", "google"],
                    search_term=keyword,
                    location=location,
                    results_wanted=results_per_query,
                    country_indeed="France",
                    linkedin_fetch_description=True,
                    job_type="fulltime",
                    verbose=0,
                )

                if df is not None and len(df) > 0:
                    for _, row in df.iterrows():
                        job = jobspy_to_standard(row.to_dict())
                        if job:
                            all_jobs.append(job)

            except Exception as e:
                print(f"   ⚠️  JobSpy '{keyword}' → {location}: {e}")

            done += 1
            time.sleep(1.5)

    return all_jobs


def deduplicate(jobs: List[Dict]) -> List[Dict]:
    """Déduplique par titre+entreprise normalisés."""
    seen: set = set()
    unique: List[Dict] = []
    for job in jobs:
        key = re.sub(
            r"\s+",
            "",
            f"{job.get('title', '').lower()}@{job.get('company', '').lower()}",
        )
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


def scan_all_france(
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> List[Dict]:
    """
    Point d'entrée principal.
    Scan toutes les sources, déduplique, score, filtre, trie.
    """

    def report(p: float, msg: str) -> None:
        if progress_callback:
            try:
                progress_callback(min(p, 1.0), msg)
            except Exception:
                pass

    report(0.02, "🚀 Lecture de la configuration...")
    config = load_config()
    profile = load_master_profile()

    keywords: List[str] = config["search"]["keywords"]
    locations: List[str] = config["search"]["locations"]
    min_score: int = int(config["filters"].get("min_score", 40))

    report(0.04, f"🔍 {len(keywords)} requêtes × {len(locations)} zones...")

    jobspy_jobs = scan_with_jobspy(
        keywords=keywords,
        locations=locations,
        progress_callback=progress_callback,
    )
    report(0.90, f"✅ JobSpy : {len(jobspy_jobs)} offres")

    all_jobs = jobspy_jobs
    report(0.92, f"🔄 Déduplication ({len(all_jobs)} brut)...")
    unique_jobs = deduplicate(all_jobs)
    report(0.94, f"✅ {len(unique_jobs)} offres uniques")

    report(0.96, "⭐ Scoring en cours...")
    scored = [score_job(job, profile, config) for job in unique_jobs]

    scored = [j for j in scored if j["fit_score"] >= min_score]
    scored.sort(key=lambda x: x["fit_score"], reverse=True)

    report(1.0, f"✅ {len(scored)} offres qualifiées prêtes !")
    return scored
