"""
Tests pour engine.sourcing.orchestrator.scan_jobs().

Couvre 5 chemins critiques sans dépendre du réseau :
  1) Mode dégradé (toutes sources désactivées) → résultat vide propre.
  2) Mode "no-credentials" (sources activées mais clés API absentes) →
     warnings clairs côté UI, pas de crash.
  3) Format des jobs renvoyés (champs attendus + types).
  4) Agrégation + déduplication multi-sources.
  5) Isolation des erreurs : une source qui crashe n'arrête pas le pipeline.
  6) list_target_profiles() : structure stable pour l'UI.

Toutes les sources réseau (`france_travail.search`, `adzuna.search`,
`companies_watcher.search`) ainsi que `requests.get` / `requests.post`
sont mockées : aucune requête HTTP réelle n'est émise.
"""

from __future__ import annotations

import os
from typing import Dict
from unittest.mock import patch

import pytest

from engine.sourcing import adzuna, companies_watcher, france_travail, orchestrator


def _job(title: str, company: str, source: str, url: str, **overrides) -> Dict:
    base = {
        "id": f"{source}-{abs(hash(url))}",
        "title": title,
        "company": company,
        "location": "Paris (75)",
        "country": "France",
        "url": url,
        "source": source,
        "description": "Ingénieur simulation numérique CFD Ansys Python.",
        "posted_date": "2026-04-20",
        "salary": "",
        "remote": False,
        "job_type": "CDI",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────
#  1. Mode dégradé : toutes sources désactivées
# ──────────────────────────────────────────────────────────────────

def test_scan_jobs_all_sources_disabled_returns_empty_clean():
    """enable_*=False → 0 jobs, structure cohérente, pas d'exception."""
    res = orchestrator.scan_jobs(
        enable_france_travail=False,
        enable_adzuna=False,
        enable_companies_watcher=False,
        use_llm_expansion=False,
        use_llm_rerank=False,
        use_llm_skills=False,
    )
    assert isinstance(res, dict)
    assert res["jobs"] == []
    assert isinstance(res.get("by_source", {}), dict)
    assert isinstance(res.get("warnings", []), list)
    assert "summary" in res


# ──────────────────────────────────────────────────────────────────
#  2. Mode "no-credentials" : warnings clairs, pas de crash
# ──────────────────────────────────────────────────────────────────

def test_scan_jobs_no_credentials_emits_clear_warnings(monkeypatch):
    """France Travail + Adzuna activés mais clés absentes → warnings UI clairs."""
    # On purge toutes les variables d'auth pour simuler un environnement vierge.
    for var in ("FT_CLIENT_ID", "FT_CLIENT_SECRET",
                "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
        monkeypatch.delenv(var, raising=False)

    # Le watcher ne nécessite pas de clé : on le neutralise pour isoler le test.
    with patch.object(companies_watcher, "search", return_value=[]):
        # Sécurité supplémentaire : aucune requête HTTP ne doit fuiter.
        with patch("requests.get", side_effect=AssertionError("network blocked")), \
             patch("requests.post", side_effect=AssertionError("network blocked")):
            res = orchestrator.scan_jobs(
                enable_france_travail=True,
                enable_adzuna=True,
                enable_companies_watcher=True,
                use_llm_expansion=False,
                use_llm_rerank=False,
                use_llm_skills=False,
            )

    assert isinstance(res, dict)
    warnings_text = " ".join(res.get("warnings") or [])
    assert "France Travail" in warnings_text
    assert "FT_CLIENT_ID" in warnings_text
    assert "Adzuna" in warnings_text
    assert "ADZUNA_APP_ID" in warnings_text
    # Le pipeline ne doit pas planter et doit renvoyer une structure valide.
    assert isinstance(res.get("jobs", []), list)


# ──────────────────────────────────────────────────────────────────
#  3. Format des jobs renvoyés
# ──────────────────────────────────────────────────────────────────

def test_scan_jobs_returned_job_format():
    """Chaque job en sortie expose les champs attendus avec les bons types."""
    jobs_in = [
        _job("Ingénieur CFD", "Airbus", "france_travail", "https://ft/1"),
        _job("Data Scientist", "Acme", "adzuna", "https://adz/1"),
    ]

    with patch.object(france_travail, "search", return_value=[jobs_in[0]]), \
         patch.object(adzuna, "search", return_value=[jobs_in[1]]), \
         patch.object(companies_watcher, "search", return_value=[]):
        res = orchestrator.scan_jobs(
            use_llm_expansion=False,
            use_llm_rerank=False,
            use_llm_skills=False,
        )

    assert isinstance(res["jobs"], list)
    assert len(res["jobs"]) >= 1
    for job in res["jobs"]:
        assert isinstance(job.get("title"), str) and job["title"]
        assert isinstance(job.get("company"), str)
        assert isinstance(job.get("url"), str)
        assert isinstance(job.get("source"), str)
        assert "fit_score" in job
        assert isinstance(job["fit_score"], (int, float))
        assert 0 <= job["fit_score"] <= 100
        assert isinstance(job.get("matched_skills", []), list)


# ──────────────────────────────────────────────────────────────────
#  4. Agrégation + déduplication
# ──────────────────────────────────────────────────────────────────

def test_scan_jobs_aggregates_and_deduplicates_across_sources():
    """3 jobs (dont 1 doublon entre FT et Adzuna) → exactement 2 en sortie."""
    duplicate_ft = _job("Ingénieur CFD", "Airbus", "france_travail", "https://ft/1")
    duplicate_adz = _job("Ingénieur CFD", "Airbus", "adzuna", "https://adz/1")
    unique = _job("Data Scientist", "Acme", "france_travail", "https://ft/2")

    with patch.object(france_travail, "search", return_value=[duplicate_ft, unique]), \
         patch.object(adzuna, "search", return_value=[duplicate_adz]), \
         patch.object(companies_watcher, "search", return_value=[]):
        res = orchestrator.scan_jobs(
            use_llm_expansion=False,
            use_llm_rerank=False,
            use_llm_skills=False,
        )

    titles = [j["title"] for j in res["jobs"]]
    # Le doublon CFD@Airbus est fusionné : "Ingénieur CFD" n'apparaît qu'une fois.
    assert titles.count("Ingénieur CFD") == 1
    assert "Data Scientist" in titles
    # 3 jobs en entrée (2 FT + 1 Adzuna), 1 doublon strict → exactement 2 en sortie.
    assert len(res["jobs"]) == 2

    # by_source doit refléter les compteurs bruts par source (avant dédup).
    by_source = res.get("by_source", {})
    assert by_source.get("france_travail") == 2
    assert by_source.get("adzuna") == 1


# ──────────────────────────────────────────────────────────────────
#  5. Isolation des erreurs source
# ──────────────────────────────────────────────────────────────────

def test_scan_jobs_source_failure_is_isolated():
    """Une source qui crashe ne doit pas faire tomber le pipeline global."""
    def _boom(*a, **kw):
        raise RuntimeError("boom")

    survivor = _job("Ingénieur CFD", "Airbus", "adzuna", "https://adz/1")

    with patch.object(france_travail, "search", side_effect=_boom), \
         patch.object(adzuna, "search", return_value=[survivor]), \
         patch.object(companies_watcher, "search", return_value=[]):
        res = orchestrator.scan_jobs(
            use_llm_expansion=False,
            use_llm_rerank=False,
            use_llm_skills=False,
        )

    assert isinstance(res, dict)
    titles = [j["title"] for j in res["jobs"]]
    assert "Ingénieur CFD" in titles


# ──────────────────────────────────────────────────────────────────
#  6. list_target_profiles : forme stable pour l'UI
# ──────────────────────────────────────────────────────────────────

def test_list_target_profiles_returns_dicts():
    """list_target_profiles() doit renvoyer des dicts {key, headline, target_keywords}."""
    profs = orchestrator.list_target_profiles()
    assert isinstance(profs, list)
    for p in profs:
        assert "key" in p and isinstance(p["key"], str)
        assert "headline" in p
        assert "target_keywords" in p and isinstance(p["target_keywords"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
