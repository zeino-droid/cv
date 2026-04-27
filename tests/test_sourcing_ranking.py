"""
Tests pour engine.sourcing.ranking — couvrent la logique pure (offline) :

  • Alias de compétences (FEM = EF = Éléments Finis = FEA…)
  • Scoring heuristique : skills, premium keywords, location, freshness,
    pénalité stage/alternance.
  • Déduplication multi-niveaux (URL, signature, Jaccard ≥ 0.75).

Aucune requête réseau n'est émise : `requests.get` / `requests.post` sont
neutralisés par sécurité, et toutes les fonctions testées sont déterministes.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict
from unittest.mock import patch

import pytest

from engine.sourcing import ranking


# ──────────────────────────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _block_network():
    """Filet de sécurité : aucun test de ranking ne doit toucher au réseau."""
    with patch("requests.get", side_effect=AssertionError("network blocked")), \
         patch("requests.post", side_effect=AssertionError("network blocked")):
        yield


@pytest.fixture
def profile() -> Dict:
    return {
        "personal_info": {
            "headline_default": "Ingénieur Simulation",
            "summary_default": "EF, CFD, jumeaux numériques.",
        },
        "skills_taxonomy": {
            "hard_skills": [
                {"name": "Éléments finis"},
                {"name": "CFD"},
                {"name": "Python"},
                {"name": "Abaqus"},
            ],
            "domain_knowledge": ["Thermomécanique"],
        },
    }


@pytest.fixture
def config() -> Dict:
    return {
        "search": {},
        "filters": {
            "min_score": 20,
            "exclude_keywords": ["stage", "stagiaire", "alternance"],
        },
        "scoring": {
            "base_score": 20,
            "per_skill_match": 8,
            "premium_keywords": {
                "simulation": 5,
                "Abaqus": 6,
                "Python": 4,
            },
            "preferred_locations": ["paris", "lyon", "grenoble"],
            "location_bonus": 5,
            "stage_penalty": -50,
        },
    }


def _job(**overrides) -> Dict:
    base = {
        "title": "Ingénieur simulation numérique",
        "company": "Airbus",
        "location": "Paris (75)",
        "description": "Simulation CFD et éléments finis sous Abaqus, scripting Python.",
        "url": "https://example.com/job/1",
        "source": "france_travail",
        "posted_date": date.today().isoformat(),
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────
#  ALIAS DE COMPÉTENCES
# ──────────────────────────────────────────────────────────────────

class TestSkillAliases:
    def test_canonical_resolves_to_all_aliases(self):
        variants = ranking._build_skill_variants("éléments finis")
        for alias in ("ef", "fem", "fea", "elements finis", "finite element"):
            assert alias in variants

    def test_alias_resolves_back_to_canonical(self):
        variants = ranking._build_skill_variants("FEM")
        assert "éléments finis" in variants
        assert "fea" in variants
        assert "ef" in variants

    def test_unknown_skill_returns_only_itself(self):
        variants = ranking._build_skill_variants("Quantum Computing")
        assert variants == ["quantum computing"]

    def test_alias_matches_in_scoring(self, profile, config):
        """Une offre qui mentionne 'FEM' doit matcher le skill 'Éléments finis'."""
        job = _job(
            title="Ingénieur calcul",
            description="Modélisation FEM des structures, expertise FEA bienvenue.",
        )
        scored = ranking.score_job(job, profile, config)
        assert "Éléments finis" in scored["matched_skills"]


# ──────────────────────────────────────────────────────────────────
#  SCORING HEURISTIQUE
# ──────────────────────────────────────────────────────────────────

class TestScoring:
    def test_base_score_no_match(self, profile, config):
        """Offre sans aucun signal → base_score uniquement (+ freshness éventuelle)."""
        job = _job(
            title="Comptable junior",
            description="Saisie comptable et déclarations TVA.",
            location="Brest (29)",
            posted_date="2020-01-01",  # vieux → 0 freshness
        )
        scored = ranking.score_job(job, profile, config)
        assert scored["fit_score"] == config["scoring"]["base_score"]
        assert scored["matched_skills"] == []

    def test_skill_match_adds_per_skill_bonus(self, profile, config):
        """Chaque skill matché ajoute per_skill_match (+ TITLE_BONUS si dans le titre)."""
        job_desc = _job(
            title="Comptable",  # pas de skill dans le titre
            description="Connaissance Python appréciée.",
            location="Brest (29)",
            posted_date="2020-01-01",
        )
        scored_desc = ranking.score_job(job_desc, profile, config)
        # base 20 + per_skill_match 8 + premium 'Python' 4 = 32
        assert scored_desc["fit_score"] == 32
        assert "Python" in scored_desc["matched_skills"]

        job_title = _job(
            title="Développeur Python",  # skill dans le titre → +6
            description="ERP métier.",
            location="Brest (29)",
            posted_date="2020-01-01",
        )
        scored_title = ranking.score_job(job_title, profile, config)
        # base 20 + per_skill_match 8 + TITLE_BONUS 6 + premium 'Python' 4 = 38
        assert scored_title["fit_score"] == 38
        # Le score titre est strictement supérieur grâce au TITLE_BONUS.
        assert scored_title["fit_score"] > scored_desc["fit_score"]

    def test_premium_keyword_bonus_applied(self, profile, config):
        """Un mot-clé premium présent dans la description ajoute son bonus."""
        job = _job(
            title="Comptable",
            description="Vague mention de simulation.",
            location="Brest (29)",
            posted_date="2020-01-01",
        )
        scored = ranking.score_job(job, profile, config)
        # base 20 + premium 'simulation' 5 = 25
        assert scored["fit_score"] == 25

    def test_location_bonus_applied_once(self, profile, config):
        """Une localisation préférée ajoute location_bonus, une seule fois."""
        job = _job(
            title="Comptable",
            description="—",
            location="Paris 15ème",
            posted_date="2020-01-01",
        )
        scored = ranking.score_job(job, profile, config)
        # base 20 + location_bonus 5 = 25
        assert scored["fit_score"] == 25

    def test_freshness_bonus_for_recent_posting(self, profile, config):
        """Une offre publiée aujourd'hui obtient +8."""
        job = _job(
            title="Comptable",
            description="—",
            location="Brest (29)",
            posted_date=date.today().isoformat(),
        )
        scored = ranking.score_job(job, profile, config)
        assert scored["fit_score"] == config["scoring"]["base_score"] + 8

    def test_freshness_decreases_with_age(self, profile, config):
        """Le bonus de fraîcheur diminue avec l'âge (8 → 5 → 2 → 0)."""
        for days, expected_bonus in [(1, 8), (5, 5), (10, 2), (30, 0)]:
            posted = (date.today() - timedelta(days=days)).isoformat()
            job = _job(
                title="Comptable",
                description="—",
                location="Brest (29)",
                posted_date=posted,
            )
            scored = ranking.score_job(job, profile, config)
            assert scored["fit_score"] == 20 + expected_bonus, (
                f"Pour {days} jour(s) → attendu bonus {expected_bonus}"
            )

    def test_stage_penalty_applied_only_on_title(self, profile, config):
        """'stage' dans le TITRE → pénalité ; dans la description → pas de pénalité."""
        job_title = _job(
            title="Stage ingénieur simulation",
            description="Mission CFD avec Abaqus.",
            location="Paris (75)",
            posted_date=date.today().isoformat(),
        )
        scored_title = ranking.score_job(job_title, profile, config)
        # La pénalité -50 doit ramener le score bien en-dessous d'un job senior équivalent.
        assert scored_title["fit_score"] < 20

        job_desc = _job(
            title="Ingénieur simulation",
            description="Possibilité d'encadrer un stage. Mission CFD avec Abaqus.",
            location="Paris (75)",
            posted_date=date.today().isoformat(),
        )
        scored_desc = ranking.score_job(job_desc, profile, config)
        # Pas de pénalité car 'stage' est uniquement dans la description.
        assert scored_desc["fit_score"] >= 50

    def test_score_clamped_between_0_and_100(self, profile, config):
        """Le score final est borné dans [0, 100]."""
        # Job ultra-pertinent : tous les skills + premium + location + fresh
        job = _job(
            title="Ingénieur simulation Python Abaqus CFD",
            description="Éléments finis, thermomécanique, simulation Python Abaqus, FEM, FEA.",
            location="Paris (75)",
            posted_date=date.today().isoformat(),
        )
        scored = ranking.score_job(job, profile, config)
        assert 0 <= scored["fit_score"] <= 100


# ──────────────────────────────────────────────────────────────────
#  DÉDUPLICATION MULTI-NIVEAUX
# ──────────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_identical_url_deduplicated(self):
        """Deux offres avec la même URL → on en garde une seule."""
        url = "https://example.com/job/1"
        jobs = [
            _job(url=url, title="Ingénieur CFD"),
            _job(url=url, title="Autre titre"),  # même URL → fusion
        ]
        out = ranking.deduplicate_smart(jobs)
        assert len(out) == 1

    def test_identical_signature_deduplicated(self):
        """Même titre+entreprise+ville mais URLs différentes → fusion."""
        jobs = [
            _job(url="https://a/1", title="Ingénieur CFD",
                 company="Airbus", location="Toulouse"),
            _job(url="https://b/2", title="Ingénieur CFD",
                 company="Airbus", location="Toulouse"),
        ]
        out = ranking.deduplicate_smart(jobs)
        assert len(out) == 1

    def test_jaccard_dedup_within_company(self):
        """Titres très proches chez même entreprise (Jaccard ≥ 0.75) → fusion.

        Tokens "ingenieur simulation numerique cfd" vs
        "ingenieur simulation numerique cfd senior" : 4 communs / 5 union = 0.8 ≥ 0.75.
        """
        jobs = [
            _job(url="https://a/1",
                 title="Ingénieur simulation numérique CFD",
                 company="Airbus", location="Toulouse"),
            _job(url="https://a/2",
                 title="Ingénieur simulation numérique CFD senior",
                 company="Airbus", location="Toulouse"),
        ]
        out = ranking.deduplicate_smart(jobs)
        assert len(out) == 1

    def test_different_companies_not_deduplicated(self):
        """Même titre mais entreprises différentes → conservées."""
        jobs = [
            _job(url="https://a/1", title="Ingénieur CFD",
                 company="Airbus", location="Toulouse"),
            _job(url="https://b/2", title="Ingénieur CFD",
                 company="Safran", location="Toulouse"),
        ]
        out = ranking.deduplicate_smart(jobs)
        assert len(out) == 2

    def test_different_titles_same_company_kept(self):
        """Titres très différents chez même entreprise → conservés."""
        jobs = [
            _job(url="https://a/1", title="Ingénieur CFD",
                 company="Airbus", location="Toulouse"),
            _job(url="https://a/2", title="Comptable junior",
                 company="Airbus", location="Toulouse"),
        ]
        out = ranking.deduplicate_smart(jobs)
        assert len(out) == 2

    def test_empty_list_returns_empty(self):
        assert ranking.deduplicate_smart([]) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
