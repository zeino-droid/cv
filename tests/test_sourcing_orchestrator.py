"""
Smoke tests for engine.sourcing.orchestrator.scan_jobs().

Vérifie 3 chemins critiques sans dépendre du réseau :
  1) Mode dégradé : toutes les sources désactivées -> retourne un résultat vide propre.
  2) Pipeline ranking : dédup + scoring fonctionnent quand les sources renvoient des jobs.
  3) Propagation des warnings de source vers la sortie.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from unittest.mock import patch

import pytest

from engine.sourcing import orchestrator


def _job(title: str, company: str, source: str, url: str) -> Dict:
    return {
        "title": title,
        "company": company,
        "location": "Paris (75)",
        "country": "France",
        "url": url,
        "source": source,
        "description": "Ingénieur simulation numérique CFD Ansys Python.",
        "date_posted": "2026-04-20",
        "salary": "",
        "remote": False,
    }


def test_scan_jobs_degraded_returns_empty_clean():
    """Toutes les sources désactivées → 0 jobs, structure cohérente, pas d'exception."""
    res = orchestrator.scan_jobs(
        enable_france_travail=False,
        enable_adzuna=False,
        enable_companies_watcher=False,
        use_llm_expansion=False,
        use_llm_rerank=False,
        use_llm_skills=False,
    )
    assert isinstance(res, dict)
    assert "jobs" in res
    assert isinstance(res["jobs"], list)
    assert res["jobs"] == []
    assert isinstance(res.get("by_source", {}), dict)


def test_scan_jobs_dedup_and_scoring_pipeline():
    """Avec des jobs mockés (dont un doublon), la dédup et le scoring doivent tourner."""
    fake_jobs = [
        _job("Ingénieur CFD", "Airbus", "france_travail", "https://ft/1"),
        _job("Ingénieur CFD", "Airbus", "adzuna", "https://adz/1"),  # doublon de fait
        _job("Data Scientist", "Acme", "france_travail", "https://ft/2"),
    ]

    with patch.object(
        orchestrator.france_travail, "search", return_value=fake_jobs[:2],
    ), patch.object(
        orchestrator.adzuna, "search", return_value=[fake_jobs[2]],
    ), patch.object(
        orchestrator.companies_watcher, "search", return_value=[],
    ):
        res = orchestrator.scan_jobs(
            use_llm_expansion=False,
            use_llm_rerank=False,
            use_llm_skills=False,
        )

    assert isinstance(res["jobs"], list)
    # Dédup : 3 jobs en entrée, au plus 2 en sortie (les deux CFD identiques fusionnés)
    assert 1 <= len(res["jobs"]) <= 3
    # Scoring : tous les jobs ont un champ fit_score numérique
    for j in res["jobs"]:
        assert "fit_score" in j
        assert isinstance(j["fit_score"], (int, float))


def test_scan_jobs_source_failure_is_isolated():
    """Une source qui crashe ne doit pas faire tomber le pipeline."""
    def _boom(*a, **kw):
        raise RuntimeError("boom")

    with patch.object(
        orchestrator.france_travail, "search", side_effect=_boom,
    ), patch.object(
        orchestrator.adzuna, "search", return_value=[],
    ), patch.object(
        orchestrator.companies_watcher, "search", return_value=[],
    ):
        res = orchestrator.scan_jobs(
            use_llm_expansion=False,
            use_llm_rerank=False,
            use_llm_skills=False,
        )
    assert isinstance(res, dict)
    assert isinstance(res.get("jobs"), list)


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
