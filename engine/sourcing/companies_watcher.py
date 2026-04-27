"""
Companies Watcher — l'innovation du sourcing France-First.

Plutôt que de scraper passivement les agrégateurs, on monitore activement
les pages carrières des employeurs simu/R&D France via leurs APIs ATS publiques :

  • Greenhouse Job Board API (sans auth)
      GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true
      Doc : https://developers.greenhouse.io/job-board.html

  • Lever Postings API (sans auth)
      GET https://api.lever.co/v0/postings/{slug}?mode=json
      Doc : https://github.com/lever/postings-api

  • Workable Widget API (sans auth)
      GET https://apply.workable.com/api/v1/widget/accounts/{slug}
      Doc : https://workable.readme.io/reference/widget-jobs

  • SmartRecruiters Public Postings API (sans auth)
      GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100
      Doc : https://dev.smartrecruiters.com/customer-api/posting-api/

La liste d'employeurs cibles est dans `profiles/target_companies.yaml`.
Le watcher charge cette liste, interroge en parallèle, filtre les offres
qui correspondent au profil (mots-clés simu/R&D/CFD…) puis renvoie une
liste normalisée.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests
import yaml

from engine.sourcing._utils import stable_id

ROOT = Path(__file__).parent.parent.parent
TARGETS_PATH = ROOT / "profiles" / "target_companies.yaml"
TIMEOUT = 15

# Les ATS supportés par le watcher
SUPPORTED_ATS = {"greenhouse", "lever", "workable", "smartrecruiters"}

# Mots-clés "France" pour filtrer les offres internationales des grands groupes
FR_LOCATION_HINTS = (
    "france", "paris", "lyon", "toulouse", "bordeaux", "marseille", "nantes",
    "lille", "rennes", "strasbourg", "grenoble", "nice", "montpellier",
    "sophia antipolis", "aix", "metz", "nancy", "mulhouse", "clermont",
    "le havre", "rouen", "dijon", "remote", "télétravail", "teletravail",
    "hybride", "full remote", "fr-",
)


# ──────────────────────────────────────────────────────────────────
#  Chargement de la liste curatée
# ──────────────────────────────────────────────────────────────────

def load_targets() -> Dict:
    if not TARGETS_PATH.exists():
        return {"companies": [], "categories": []}
    with open(TARGETS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"companies": [], "categories": []}


def categories() -> List[Dict]:
    return load_targets().get("categories", []) or []


# ──────────────────────────────────────────────────────────────────
#  Clients ATS (un par fournisseur)
# ──────────────────────────────────────────────────────────────────

def _fetch_greenhouse(slug: str) -> List[Dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json() or {}
        return data.get("jobs", []) or []
    except Exception:
        return []


def _normalize_greenhouse(item: Dict, company: str) -> Optional[Dict]:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    location = ((item.get("location") or {}).get("name") or "").strip()
    description_html = item.get("content") or ""
    description = re.sub(r"<[^>]+>", " ", description_html)
    description = re.sub(r"&[a-z]+;", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    url = (item.get("absolute_url") or "").strip()
    posted = (item.get("updated_at") or item.get("created_at") or "")[:10]
    return {
        "id": stable_id("CW", "greenhouse", item.get("id", ""), title, company),
        "title": title,
        "company": company,
        "location": location or "France",
        "description": description,
        "url": url,
        "source": "companies_watcher",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": "CDI",
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


def _fetch_lever(slug: str) -> List[Dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        return resp.json() or []
    except Exception:
        return []


def _normalize_lever(item: Dict, company: str) -> Optional[Dict]:
    title = (item.get("text") or "").strip()
    if not title:
        return None
    cats = item.get("categories") or {}
    location = (cats.get("location") or "").strip()
    description = (item.get("descriptionPlain") or item.get("description") or "")
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    url = (item.get("hostedUrl") or item.get("applyUrl") or "").strip()
    created = item.get("createdAt")
    posted = ""
    if isinstance(created, (int, float)):
        try:
            from datetime import datetime
            posted = datetime.utcfromtimestamp(created / 1000).date().isoformat()
        except Exception:
            posted = ""
    contract = (cats.get("commitment") or "").lower()
    job_type = "CDI" if any(k in contract for k in ("full", "permanent", "cdi")) else "—"
    return {
        "id": stable_id("CW", "lever", item.get("id", ""), title, company),
        "title": title,
        "company": company,
        "location": location or "France",
        "description": description,
        "url": url,
        "source": "companies_watcher",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": job_type,
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


def _fetch_workable(slug: str) -> List[Dict]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json() or {}
        jobs = data.get("jobs") or []
        return jobs if isinstance(jobs, list) else []
    except Exception:
        return []


def _normalize_workable(item: Dict, company: str) -> Optional[Dict]:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    location = (item.get("location") or "").strip()
    if not location:
        loc_obj = item.get("country") or {}
        if isinstance(loc_obj, dict):
            location = (loc_obj.get("name") or "").strip()
    description = (item.get("description") or "")
    description = re.sub(r"<[^>]+>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    url = (item.get("url") or item.get("application_url") or "").strip()
    posted = (item.get("created_at") or item.get("published_on") or "")[:10]
    return {
        "id": stable_id("CW", "workable", item.get("shortcode", item.get("id", "")), title, company),
        "title": title,
        "company": company,
        "location": location or "France",
        "description": description,
        "url": url,
        "source": "companies_watcher",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": "CDI",
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


def _fetch_smartrecruiters(slug: str) -> List[Dict]:
    """Pagination simple — limit 100, on prend les 200 premières offres max."""
    out: List[Dict] = []
    base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    for offset in (0, 100):
        try:
            resp = requests.get(
                base,
                params={"limit": 100, "offset": offset},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                break
            data = resp.json() or {}
            chunk = data.get("content", []) or []
            if not chunk:
                break
            out.extend(chunk)
            if len(chunk) < 100:
                break
        except Exception:
            break
    return out


def _normalize_smartrecruiters(item: Dict, company: str, slug: str) -> Optional[Dict]:
    title = (item.get("name") or "").strip()
    if not title:
        return None
    loc = item.get("location") or {}
    parts = [loc.get("city") or "", loc.get("region") or "", loc.get("country") or ""]
    location = ", ".join([p for p in parts if p]).strip() or "France"
    job_ad = item.get("jobAd") or {}
    sections = (job_ad.get("sections") or {})
    description_parts = []
    for sec in ("jobDescription", "qualifications", "additionalInformation"):
        text = (sections.get(sec) or {}).get("text") or ""
        if text:
            description_parts.append(re.sub(r"<[^>]+>", " ", text))
    description = re.sub(r"\s+", " ", " ".join(description_parts)).strip()
    posting_id = item.get("id") or item.get("uuid") or ""
    url = item.get("ref") or ""
    if not url and posting_id:
        # URL canonique d'une offre SmartRecruiters
        url = f"https://jobs.smartrecruiters.com/{slug}/{posting_id}"
    posted = (item.get("releasedDate") or item.get("createdOn") or "")[:10]
    return {
        "id": stable_id("CW", "smartrecruiters", posting_id, title, company),
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "url": url,
        "source": "companies_watcher",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": "CDI",
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


# ──────────────────────────────────────────────────────────────────
#  Filtrage : France + mots-clés profil
# ──────────────────────────────────────────────────────────────────

def _is_in_france(job: Dict) -> bool:
    loc = (job.get("location") or "").lower()
    if not loc:
        # Pas de location → on garde par défaut (les ATS FR ne précisent pas toujours)
        return True
    return any(hint in loc for hint in FR_LOCATION_HINTS)


def _matches_keywords(job: Dict, keywords: List[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{job.get('title','')} {job.get('description','')}".lower()
    return any(kw.lower() in haystack for kw in keywords)


# ──────────────────────────────────────────────────────────────────
#  Orchestration interne du watcher
# ──────────────────────────────────────────────────────────────────

def _process_company(company_def: Dict) -> List[Dict]:
    name = company_def.get("name") or ""
    ats = (company_def.get("ats") or "").lower()
    slug = company_def.get("slug") or ""
    if not (name and slug and ats):
        return []
    if ats not in SUPPORTED_ATS:
        return []

    if ats == "greenhouse":
        items = _fetch_greenhouse(slug)
        return [j for j in (_normalize_greenhouse(i, name) for i in items) if j]
    if ats == "lever":
        items = _fetch_lever(slug)
        return [j for j in (_normalize_lever(i, name) for i in items) if j]
    if ats == "workable":
        items = _fetch_workable(slug)
        return [j for j in (_normalize_workable(i, name) for i in items) if j]
    if ats == "smartrecruiters":
        items = _fetch_smartrecruiters(slug)
        return [j for j in (_normalize_smartrecruiters(i, name, slug) for i in items) if j]
    return []


def search(
    keywords: Optional[List[str]] = None,
    selected_categories: Optional[List[str]] = None,
    only_france: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
    max_workers: int = 8,
) -> List[Dict]:
    """
    Interroge en parallèle les pages carrières des employeurs cibles,
    filtre par mots-clés et localisation France.

    `selected_categories` : liste d'ids de catégories (ex ["editeurs_simu", "energie"]).
                            Si None → toutes les catégories.
    """
    targets = load_targets()
    companies: List[Dict] = targets.get("companies", []) or []

    if selected_categories:
        cats = set(selected_categories)
        companies = [c for c in companies if c.get("category") in cats]

    if not companies:
        return []

    out: List[Dict] = []
    total = len(companies)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process_company, c): c for c in companies}
        for future in as_completed(futures):
            if should_stop and should_stop():
                break
            comp = futures[future]
            try:
                jobs = future.result() or []
            except Exception as exc:
                print(f"   ⚠️  Companies Watcher · {comp.get('name')}: {exc}")
                jobs = []
            kept = jobs
            if only_france:
                kept = [j for j in kept if _is_in_france(j)]
            if keywords:
                kept = [j for j in kept if _matches_keywords(j, keywords)]
            out.extend(kept)
            done += 1
            if progress_callback:
                progress_callback(
                    done / max(total, 1),
                    f"🎯 Companies Watcher · {comp.get('name')} (+{len(kept)})",
                )

    return out
