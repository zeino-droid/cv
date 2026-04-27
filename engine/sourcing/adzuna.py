"""
Client Adzuna API — agrégateur européen, complément à France Travail.

Doc : https://developer.adzuna.com/
Tarif gratuit : 1000 requêtes/mois → cache disque 24 h.

Endpoint search FR :
  GET https://api.adzuna.com/v1/api/jobs/fr/search/{page}
      ?app_id=…&app_key=…&what=…&where=…&results_per_page=50&max_days_old=30

Si ADZUNA_APP_ID / ADZUNA_APP_KEY absents : retourne [] + WARN, sans planter.
"""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Callable, Dict, List, Optional

import requests

from engine.sourcing._cache import get_cache, set_cache
from engine.sourcing._utils import stable_id

BASE_URL = "https://api.adzuna.com/v1/api/jobs/fr/search"
TIMEOUT = 20


def has_credentials() -> bool:
    return bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY"))


def _normalize(item: Dict) -> Optional[Dict]:
    title = (item.get("title") or "").strip()
    if not title:
        return None
    company = ((item.get("company") or {}).get("display_name") or "").strip() or "Entreprise"
    location = ((item.get("location") or {}).get("display_name") or "France").strip()
    description = (item.get("description") or "").strip()
    url = (item.get("redirect_url") or "").strip()
    posted = (item.get("created") or "")[:10]
    contract = (item.get("contract_time") or "").lower()
    contract_type = (item.get("contract_type") or "").lower()
    job_type = "CDI" if "perm" in contract_type or "perm" in contract else "—"

    job_id = stable_id("ADZ", item.get("id", ""), title, company)
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "url": url,
        "source": "adzuna",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": job_type,
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


def _search_one(
    what: str,
    where: str = "",
    page: int = 1,
    results_per_page: int = 50,
    max_days_old: int = 30,
    full_time: bool = False,
) -> List[Dict]:
    cache_key = f"{what}|{where}|{page}|{results_per_page}|{max_days_old}|{int(full_time)}"
    cached = get_cache("adzuna", cache_key, ttl_seconds=86400)
    if cached is not None:
        return cached

    params = {
        "app_id": os.environ["ADZUNA_APP_ID"],
        "app_key": os.environ["ADZUNA_APP_KEY"],
        "what": what,
        "results_per_page": results_per_page,
        "max_days_old": max_days_old,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where
    if full_time:
        params["full_time"] = 1

    try:
        resp = requests.get(f"{BASE_URL}/{page}", params=params, timeout=TIMEOUT)
    except Exception as exc:
        print(f"   ⚠️  Adzuna request failed: {exc}")
        return []

    if resp.status_code != 200:
        print(f"   ⚠️  Adzuna failed ({resp.status_code}) for '{what}' / '{where}': {resp.text[:200]}")
        return []

    data = resp.json() or {}
    items = data.get("results", []) or []
    normalized = [n for n in (_normalize(i) for i in items) if n]
    set_cache("adzuna", cache_key, normalized)
    return normalized


def search(
    keywords: List[str],
    locations: Optional[List[str]] = None,
    max_days_old: int = 30,
    results_per_query: int = 50,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> List[Dict]:
    """Multi-keyword × multi-location, dédupliqué par id."""
    if not has_credentials():
        print("   ⚠️  Adzuna : credentials absents (ADZUNA_APP_ID / ADZUNA_APP_KEY).")
        print("       Inscription gratuite (1000 req/mois) : https://developer.adzuna.com/")
        return []
    if not keywords:
        return []

    targets = locations or [""]  # "" = recherche nationale
    out: Dict[str, Dict] = {}

    for kw in keywords:
        if should_stop and should_stop():
            break
        for where in targets:
            if should_stop and should_stop():
                break
            if progress_callback:
                label = where or "France"
                progress_callback(0.0, f"🌍 Adzuna · {kw[:30]} → {label}")
            results = _search_one(
                what=kw,
                where=where,
                results_per_page=min(50, results_per_query),
                max_days_old=max_days_old,
            )
            for job in results:
                out[job["id"]] = job
            time.sleep(0.3)

    return list(out.values())
