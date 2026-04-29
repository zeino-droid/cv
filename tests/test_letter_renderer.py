"""
Tests pour le module engine/letter_renderer.py et l'intégration lettre PDF.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.letter_renderer import (
    LetterRenderer,
    build_letter_data,
    format_french_date,
    save_letter_text_fallback,
    FORMULES_POLITESSE,
)


# ─── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_profile():
    return {
        "personal_info": {
            "name": "Zein ELAJAMY",
            "email": "zeinfrance4@gmail.com",
            "phone": "+33 7 54 45 47 42",
            "location": "France (mobilité nationale)",
        },
        "education": [
            {
                "degree": "Diplôme d'Ingénieur",
                "institution": "ENSEM (École Nationale Supérieure) — INP Lorraine",
            }
        ],
        "experience_stark": [
            {
                "id": "AM_PFE",
                "title": "PFE : Flambage Dynamique",
                "company": "ArcelorMittal R&D",
                "A": "Validé la méthodologie sur le cas test de Scordelis-Lo.",
                "K": ["Abaqus", "Flambage", "Éléments Finis"],
            }
        ],
    }


@pytest.fixture
def sample_job():
    return {
        "id": "test_001",
        "title": "Ingénieur Calcul de Structures",
        "company": "Safran Aircraft Engines",
        "location": "Paris",
        "description": "Vous rejoindrez l'équipe de calcul structures...",
        "required_skills": ["Abaqus", "Éléments Finis"],
    }


# ─── Tests format_french_date ────────────────────────────────────

def test_french_date_format():
    dt = datetime(2026, 4, 29)
    result = format_french_date(dt)
    assert result == "29 avril 2026"


def test_french_date_january():
    dt = datetime(2026, 1, 1)
    result = format_french_date(dt)
    assert result == "1 janvier 2026"


def test_french_date_none_uses_now():
    result = format_french_date()
    assert isinstance(result, str)
    # Should contain the current year
    assert str(datetime.now().year) in result


# ─── Tests build_letter_data ─────────────────────────────────────

def test_build_letter_data_structure(sample_profile, sample_job):
    paragraphs = ["P1 test", "P2 test", "P3 test", "P4 test"]
    result = build_letter_data(sample_profile, sample_job, paragraphs)

    # Vérifie les champs obligatoires
    assert "sender" in result
    assert "recipient" in result
    assert "paragraphs" in result
    assert "closing_formula" in result
    assert "signature_name" in result
    assert "city" in result
    assert "date" in result
    assert "subject" in result


def test_build_letter_data_sender_from_profile(sample_profile, sample_job):
    result = build_letter_data(sample_profile, sample_job, ["Test"])
    assert result["sender"]["name"] == "Zein ELAJAMY"
    assert result["sender"]["email"] == "zeinfrance4@gmail.com"
    assert result["sender"]["phone"] == "+33 7 54 45 47 42"


def test_build_letter_data_recipient_from_job(sample_profile, sample_job):
    result = build_letter_data(sample_profile, sample_job, ["Test"])
    assert result["recipient"]["company"] == "Safran Aircraft Engines"


def test_build_letter_data_subject_contains_title(sample_profile, sample_job):
    result = build_letter_data(sample_profile, sample_job, ["Test"])
    assert "Ingénieur Calcul de Structures" in result["subject"]


def test_build_letter_data_default_closing(sample_profile, sample_job):
    result = build_letter_data(sample_profile, sample_job, ["Test"])
    assert result["closing_formula"] == FORMULES_POLITESSE[0]
    assert "salutations distinguées" in result["closing_formula"]


def test_build_letter_data_custom_closing(sample_profile, sample_job):
    custom = "Veuillez agréer mes salutations."
    result = build_letter_data(
        sample_profile, sample_job, ["Test"],
        closing_formula=custom,
    )
    assert result["closing_formula"] == custom


def test_build_letter_data_paragraphs(sample_profile, sample_job):
    paragraphs = ["Accroche", "Valeur", "Motivation", "CTA"]
    result = build_letter_data(sample_profile, sample_job, paragraphs)
    assert result["paragraphs"] == paragraphs
    assert len(result["paragraphs"]) == 4


# ─── Tests save_letter_text_fallback ─────────────────────────────

def test_save_text_fallback(tmp_path):
    text = "Contenu de la lettre de test."
    out = tmp_path / "output" / "lettre"
    result = save_letter_text_fallback(text, out)
    assert result.suffix == ".txt"
    assert result.exists()
    assert result.read_text(encoding="utf-8") == text


# ─── Tests LetterRenderer ────────────────────────────────────────

def test_renderer_unavailable_without_typst():
    with patch("engine.letter_renderer.typst", None):
        renderer = LetterRenderer()
        renderer.available = False
        result = renderer.render({"test": "data"}, Path("/tmp/test.pdf"))
        assert result is None


def test_renderer_missing_template():
    renderer = LetterRenderer(template_path=Path("/nonexistent/template.typ"))
    renderer.available = True
    result = renderer.render({"test": "data"}, Path("/tmp/test.pdf"))
    assert result is None


# ─── Tests Pipeline intégration ──────────────────────────────────

def test_heuristic_contains_vous_moi_nous(sample_profile, sample_job):
    """Vérifie que l'heuristique produit une lettre avec la structure VOUS→MOI→NOUS."""
    from Pipeline import generate_cover_letter_heuristic

    result = generate_cover_letter_heuristic(sample_profile, sample_job)

    # La lettre doit contenir le nom de l'entreprise
    assert "Safran Aircraft Engines" in result
    # La lettre doit contenir le titre du poste
    assert "Ingénieur Calcul de Structures" in result
    # La lettre doit contenir la formule de politesse longue
    assert "salutations distinguées" in result
    # La lettre ne doit PAS contenir les mots interdits
    assert "Apprenti" not in result
    assert "Étudiant" not in result
    assert "Élève" not in result
    # La lettre ne doit PAS contenir "Cordialement"
    assert "Cordialement" not in result


def test_heuristic_paragraphs_structured(sample_profile, sample_job):
    """Vérifie que generate_cover_letter_paragraphs_heuristic retourne 4 paragraphes."""
    from Pipeline import generate_cover_letter_paragraphs_heuristic

    result = generate_cover_letter_paragraphs_heuristic(sample_profile, sample_job)
    assert isinstance(result, list)
    assert len(result) == 4
    # Chaque paragraphe doit être non-vide
    for p in result:
        assert isinstance(p, str)
        assert len(p) > 10


def test_french_date_in_letter_data(sample_profile, sample_job):
    """Vérifie que la date dans letter_data est au format français."""
    result = build_letter_data(sample_profile, sample_job, ["Test"])
    # La date doit être du type "29 avril 2026" (pas 29/04/2026)
    assert "/" not in result["date"]
    # Doit contenir un mois en français
    french_months = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    assert any(m in result["date"] for m in french_months)
