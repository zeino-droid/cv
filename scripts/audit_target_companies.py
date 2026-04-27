"""
Audit script for profiles/target_companies.yaml.

Pour chaque entrée, ping l'API ATS publique correspondante et reporte :
  - HTTP status
  - Nombre d'offres renvoyées
  - Nombre d'offres "France" (filtre lâche : présence d'un marqueur FR)
  - Échantillon d'intitulés/locations

Usage:
    python scripts/audit_target_companies.py [slug_to_test]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import requests
import yaml

ROOT = Path(__file__).parent.parent
TARGETS = ROOT / "profiles" / "target_companies.yaml"

TIMEOUT = 20

# Marqueurs FR utilisés par l'audit (calqués sur engine/sourcing/companies_watcher.py
# pour rester cohérent : pas de bare "fr" car "Frankfurt"/"Friburg" matcheraient).
FR_MARKERS = (
    "france", "paris", "lyon", "toulouse", "bordeaux", "marseille", "nantes",
    "lille", "rennes", "strasbourg", "grenoble", "nice", "montpellier",
    "sophia antipolis", "aix-en-provence", "metz", "nancy", "mulhouse",
    "clermont-ferrand", "le havre", "rouen", "dijon", "valbonne",
    "île-de-france", "ile-de-france", "hauts-de-france", "nouvelle-aquitaine",
    "occitanie", "provence", "bretagne", "normandie", "alsace", "auvergne",
    "rhône-alpes", "rhone-alpes", "pays de la loire", "centre-val de loire",
    "grand est", "bourgogne", "fr-", ", fr", "(fr)", " fr ",
)

# Marqueurs "non-FR" qui doivent disqualifier même si un mot ambigu est présent.
NON_FR_BLOCKERS = (
    "united states", "usa", "united kingdom", " uk ", "(uk)", "germany",
    "deutschland", "frankfurt", "berlin", "münchen", "munich", "spain",
    "españa", "madrid", "barcelona", "italy", "italia", "milan", "milano",
    "roma", "netherlands", "amsterdam", "rotterdam", "belgium", "brussels",
    "bruxelles", "switzerland", "zurich", "geneva", "genève", "ireland",
    "dublin", "poland", "warsaw", "warszawa", "portugal", "lisbon", "lisboa",
    "porto", "canada", "toronto", "montreal", "montréal", "india", "bangalore",
    "bengaluru", "mumbai", "singapore", "japan", "tokyo", "australia",
    "sydney", "emea", "amer", "apac", "latam",
)


def _is_fr(loc: str) -> bool:
    """Heuristique cohérente avec engine/sourcing/companies_watcher.py._is_in_france."""
    s = f" {(loc or '').lower()} "
    if any(b in s for b in NON_FR_BLOCKERS):
        return False
    return any(m in s for m in FR_MARKERS)


def audit_greenhouse(slug: str) -> Tuple[int, int, int, List[str]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code != 200:
        return resp.status_code, 0, 0, []
    jobs = (resp.json() or {}).get("jobs", []) or []
    fr = [j for j in jobs if _is_fr(((j.get("location") or {}).get("name") or ""))]
    sample = [
        f"{j.get('title','?')[:60]}  ::  {((j.get('location') or {}).get('name') or '?')}"
        for j in fr[:5]
    ]
    return 200, len(jobs), len(fr), sample


def audit_lever(slug: str) -> Tuple[int, int, int, List[str]]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code != 200:
        return resp.status_code, 0, 0, []
    jobs = resp.json() or []
    fr = [
        j for j in jobs
        if _is_fr(((j.get("categories") or {}).get("location") or ""))
    ]
    sample = [
        f"{(j.get('text') or '?')[:60]}  ::  {((j.get('categories') or {}).get('location') or '?')}"
        for j in fr[:5]
    ]
    return 200, len(jobs), len(fr), sample


def audit_workable(slug: str) -> Tuple[int, int, int, List[str]]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}?details=true"
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code != 200:
        return resp.status_code, 0, 0, []
    data = resp.json() or {}
    jobs = data.get("jobs") or []
    fr = [j for j in jobs if _is_fr(j.get("location") or "") or _is_fr(((j.get("country") or {}).get("name") if isinstance(j.get("country"), dict) else "") or "")]
    sample = [
        f"{(j.get('title') or '?')[:60]}  ::  {(j.get('location') or '?')}"
        for j in fr[:5]
    ]
    return 200, len(jobs), len(fr), sample


def audit_smartrecruiters(slug: str) -> Tuple[int, int, int, List[str]]:
    out: List[Dict] = []
    last_status = 0
    for offset in (0, 100, 200):
        try:
            resp = requests.get(
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                params={"limit": 100, "offset": offset},
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            return -1, 0, 0, [f"EXC: {exc}"]
        last_status = resp.status_code
        if resp.status_code != 200:
            return resp.status_code, 0, 0, []
        chunk = (resp.json() or {}).get("content", []) or []
        out.extend(chunk)
        if len(chunk) < 100:
            break
    fr = []
    for j in out:
        loc = j.get("location") or {}
        loc_str = " ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")]))
        if _is_fr(loc_str):
            fr.append((j, loc_str))
    sample = [
        f"{(j.get('name') or '?')[:60]}  ::  {loc_str}"
        for j, loc_str in fr[:5]
    ]
    return last_status, len(out), len(fr), sample


AUDITORS = {
    "greenhouse": audit_greenhouse,
    "lever": audit_lever,
    "workable": audit_workable,
    "smartrecruiters": audit_smartrecruiters,
}


def audit_one(name: str, ats: str, slug: str) -> Dict:
    auditor = AUDITORS.get(ats)
    if not auditor:
        return {
            "name": name, "ats": ats, "slug": slug,
            "status": "SKIP", "total": 0, "fr": 0, "sample": [],
        }
    try:
        status, total, fr, sample = auditor(slug)
    except Exception as exc:
        return {
            "name": name, "ats": ats, "slug": slug,
            "status": f"EXC: {exc.__class__.__name__}", "total": 0, "fr": 0, "sample": [],
        }
    return {
        "name": name, "ats": ats, "slug": slug,
        "status": status, "total": total, "fr": fr, "sample": sample,
    }


def main() -> None:
    data = yaml.safe_load(TARGETS.read_text(encoding="utf-8")) or {}
    companies = data.get("companies", []) or []

    # Mode "test single slug" : python audit ats slug
    if len(sys.argv) == 3:
        ats, slug = sys.argv[1], sys.argv[2]
        result = audit_one(slug, ats, slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print(f"Auditing {len(companies)} companies from {TARGETS}\n")
    for c in companies:
        r = audit_one(c.get("name", "?"), (c.get("ats") or "").lower(), c.get("slug") or "")
        flag = "OK " if (r["total"] > 0 and r["status"] == 200) else "!! "
        print(f"{flag}[{r['status']}] {r['name']:35s} ats={r['ats']:16s} slug={r['slug']:25s} total={r['total']:4d}  fr={r['fr']:4d}")
        for s in r["sample"][:3]:
            print(f"      · {s}")
    print("\nDone.")


if __name__ == "__main__":
    main()
