"""Smoke tests pour engine.section_rewrite : extraction, prompt, parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.section_rewrite import (
    EDITABLE_SECTIONS,
    build_section_prompt,
    extract_current,
    extract_source,
    find_unapplied_overrides,
    list_experience_items,
    list_project_items,
    list_section_keys,
    parse_section_value,
)


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture(scope="module")
def profile():
    """Le vrai profil maître — on teste sur la donnée réelle."""
    p = json.loads((ROOT / "profiles" / "master_profile.json").read_text(encoding="utf-8"))
    return p


@pytest.fixture
def cv_data():
    """Mock d'un CV courant (résultat d'une génération)."""
    return {
        "headline": "Ingénieur Simulation Numérique | EF · CFD",
        "summary": "Expert en modélisation thermomécanique avec Abaqus et Python.",
        "experiences": [
            {
                "id": "AM_PFE",
                "position": "PFE Flambage Dynamique",
                "company": "ArcelorMittal",
                "achievements": ["Puce existante 1", "Puce existante 2"],
            },
            {
                "id": "AM_A1",
                "position": "Apprenti R&D",
                "company": "ArcelorMittal",
                "achievements": ["Puce A1.1"],
            },
        ],
        "projects": [
            {"id": "ENSEM_PROJ_FLUENT", "name": "NACA 23012",
             "description": "Simulation CFD aile.", "keywords": "Fluent · CFD · Maillage"},
        ],
        "grouped_skills": {
            "Compétences Techniques": [{"name": "Abaqus"}, {"name": "Python"}],
            "Connaissances Métier": [{"name": "Modélisation thermique"}],
            "Savoir-être": [{"name": "Adaptabilité"}],
        },
    }


@pytest.fixture
def job():
    return {
        "title": "Ingénieur R&D Simulation",
        "company": "Test Co",
        "location": "Lyon",
        "description": "Recherche ingénieur CFD/EF avec Python.",
        "matched_skills": ["CFD", "Python", "Abaqus"],
    }


# ============================================================
# 1. Catalogue EDITABLE_SECTIONS bien formé
# ============================================================
def test_editable_sections_schema_complete():
    """Chaque section doit avoir les clés essentielles pour piloter UI + LLM."""
    required = {"icon", "label", "value_type", "per_item", "prompt_role", "format_rules"}
    for key, spec in EDITABLE_SECTIONS.items():
        missing = required - set(spec.keys())
        assert not missing, f"Section '{key}' manque les clés : {missing}"
        assert spec["value_type"] in ("str", "list_str", "str_dot_separated"), (
            f"value_type inconnu pour '{key}': {spec['value_type']}"
        )


def test_per_item_sections_listed():
    per_item = list_section_keys(per_item_only=True)
    assert "achievements" in per_item
    assert "project_description" in per_item
    assert "headline" not in per_item


# ============================================================
# 2. Extraction source profil
# ============================================================
def test_extract_source_summary(profile):
    src = extract_source(profile, "summary")
    assert src["raw"]
    assert isinstance(src["raw"], str)


def test_extract_source_achievements_real_id(profile):
    """Avec un id existant dans le profil."""
    src = extract_source(profile, "achievements", item_id="AM_PFE")
    assert src["raw"] is not None
    raw = src["raw"]
    assert raw["id"] == "AM_PFE"
    assert "Action" in raw and "Resultat" in raw


def test_extract_source_achievements_unknown_id(profile):
    src = extract_source(profile, "achievements", item_id="DOES_NOT_EXIST")
    assert src["raw"] is None


def test_extract_source_skills(profile):
    for key in ("skills_hard", "skills_domain", "skills_soft"):
        src = extract_source(profile, key)
        assert src["raw"] is not None
        assert isinstance(src["raw"], list)


def test_extract_source_per_item_without_id_returns_empty(profile):
    """Sans item_id, les sections per_item doivent renvoyer un vide propre."""
    src = extract_source(profile, "achievements", item_id=None)
    assert src["raw"] is None
    assert src["json_dump"] == ""


# ============================================================
# 3. Extraction current depuis cv_data
# ============================================================
def test_extract_current_headline_summary(cv_data):
    assert extract_current(cv_data, "headline").startswith("Ingénieur")
    assert extract_current(cv_data, "summary").startswith("Expert")


def test_extract_current_achievements_by_id(cv_data):
    val = extract_current(cv_data, "achievements", item_id="AM_PFE")
    assert val == ["Puce existante 1", "Puce existante 2"]


def test_extract_current_skills_groups(cv_data):
    assert extract_current(cv_data, "skills_hard") == ["Abaqus", "Python"]
    assert extract_current(cv_data, "skills_domain") == ["Modélisation thermique"]
    assert extract_current(cv_data, "skills_soft") == ["Adaptabilité"]


def test_list_items(cv_data):
    exps = list_experience_items(cv_data)
    assert len(exps) == 2
    assert exps[0]["id"] == "AM_PFE"
    projs = list_project_items(cv_data)
    assert len(projs) == 1
    assert projs[0]["id"] == "ENSEM_PROJ_FLUENT"


# ============================================================
# 4. Construction prompt — sanity check
# ============================================================
def test_build_section_prompt_contains_essentials(profile, cv_data, job):
    src = extract_source(profile, "achievements", item_id="AM_PFE")
    cur = extract_current(cv_data, "achievements", item_id="AM_PFE")
    prompt = build_section_prompt(
        section_key="achievements",
        source=src,
        current=cur,
        job=job,
        instruction="Mets l'accent sur le calcul Abaqus.",
    )
    assert "Mets l'accent sur le calcul Abaqus" in prompt
    assert "Test Co" in prompt
    assert "JSON strict" in prompt or "items" in prompt
    # Doit contenir au moins un mot du STAR-K source
    assert "AM_PFE" in prompt or "Action" in prompt


def test_build_section_prompt_for_str_type(profile, cv_data, job):
    src = extract_source(profile, "summary")
    cur = extract_current(cv_data, "summary")
    prompt = build_section_prompt(
        section_key="summary",
        source=src,
        current=cur,
        job=job,
        instruction="Ajoute une mention CFD.",
    )
    assert "résumé" in prompt.lower()
    assert "Ajoute une mention CFD" in prompt


# ============================================================
# 5. Parsing typé
# ============================================================
def test_parse_str_strips_preamble():
    val, err = parse_section_value("summary", 'Voici le résumé : "Bla bla bla"')
    assert err is None
    assert "Bla bla bla" in val
    # le préambule doit être retiré
    assert "Voici" not in val


def test_parse_list_str_from_clean_json():
    raw = '{"items": ["puce 1 long", "puce 2", "puce 3"]}'
    val, err = parse_section_value("achievements", raw)
    assert err is None
    assert isinstance(val, list)
    assert len(val) == 2  # max_items pour achievements
    assert val[0] == "puce 1 long"


def test_parse_list_str_from_markdown_bullets():
    """Le LLM renvoie parfois des bullets markdown au lieu de JSON."""
    raw = "- Puce numéro 1\n- Puce numéro 2\n- Puce numéro 3"
    val, err = parse_section_value("achievements", raw)
    assert err is None
    assert val == ["Puce numéro 1", "Puce numéro 2"]  # capé à 2


def test_parse_list_str_skills_hard_keeps_more():
    raw = '{"items": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"]}'
    val, err = parse_section_value("skills_hard", raw)
    assert err is None
    assert len(val) == 12  # max_items pour skills_hard


def test_parse_str_dot_separated_from_comma():
    raw = "Fluent, CFD, Maillage, NACA"
    val, err = parse_section_value("project_keywords", raw)
    assert err is None
    assert " · " in val
    assert "Fluent" in val


def test_parse_empty_returns_error():
    val, err = parse_section_value("summary", "")
    assert val is None
    assert err


# ============================================================
# 6. Letter handling — extract_current("letter")
# ============================================================
def test_extract_current_letter_reads_letter_text():
    cv_data = {"letter_text": "Madame, Monsieur, ..."}
    assert extract_current(cv_data, "letter") == "Madame, Monsieur, ..."


def test_extract_current_letter_missing_returns_empty():
    assert extract_current({}, "letter") == ""


# ============================================================
# 7. find_unapplied_overrides — UX warning helper
# ============================================================
def test_find_unapplied_overrides_empty():
    assert find_unapplied_overrides({}, {}) == []
    assert find_unapplied_overrides({"experiences": []}, {}) == []


def test_find_unapplied_overrides_detects_missing_exp(cv_data):
    overrides = {"achievements": {"AM_PFE": ["x"], "GHOST": ["y"]}}
    msgs = find_unapplied_overrides(cv_data, overrides)
    assert len(msgs) == 1
    assert "GHOST" in msgs[0]


def test_find_unapplied_overrides_detects_missing_proj(cv_data):
    overrides = {
        "project_description": {"ENSEM_PROJ_FLUENT": "ok", "GHOST_PROJ": "x"},
        "project_keywords": {"GHOST_PROJ": "kw"},
    }
    msgs = find_unapplied_overrides(cv_data, overrides)
    assert len(msgs) == 2
    assert all("GHOST_PROJ" in m for m in msgs)


def test_find_unapplied_overrides_all_match(cv_data):
    overrides = {
        "achievements": {"AM_PFE": ["x"]},
        "project_description": {"ENSEM_PROJ_FLUENT": "ok"},
        "skills_hard": ["A", "B"],  # liste plate, jamais "non matchée"
    }
    assert find_unapplied_overrides(cv_data, overrides) == []


# ============================================================
# 8. Test d'intégration — overrides traversent vraiment cv_generator
# ============================================================
def test_apply_text_overrides_per_item():
    """Garantit que _apply_text_overrides applique les puces par exp_id."""
    from engine.cv_generator import PersonalCVGenerator

    gen = PersonalCVGenerator()
    cv_data = {
        "headline": "h0",
        "summary": "s0",
        "experiences": [
            {"id": "AM_PFE", "position": "PFE", "achievements": ["old1", "old2"]},
            {"id": "AM_A1", "position": "A1", "achievements": ["a1.old"]},
        ],
        "projects": [
            {"id": "P1", "name": "P1", "description": "old desc", "keywords": "old · kw"},
        ],
        "grouped_skills": {
            "Compétences Techniques": [{"name": "Old"}],
        },
    }
    overrides = {
        "headline": "NEW HEADLINE",
        "achievements": {"AM_PFE": ["new1", "new2", ""]},
        "project_description": {"P1": "new desc"},
        "project_keywords": {"P1": "new · kw"},
        "skills_hard": ["X", "Y", "Z"],
        "skills_soft": ["Adapt"],
    }
    out = gen._apply_text_overrides(cv_data, section_overrides=overrides)

    assert out["headline"] == "NEW HEADLINE"
    # AM_PFE écrasé, AM_A1 inchangé
    by_id = {e["id"]: e for e in out["experiences"]}
    assert by_id["AM_PFE"]["achievements"] == ["new1", "new2"]  # vide skipé
    assert by_id["AM_A1"]["achievements"] == ["a1.old"]
    # Projet écrasé
    assert out["projects"][0]["description"] == "new desc"
    assert out["projects"][0]["keywords"] == "new · kw"
    # Skills hard remplacés, soft ajouté
    grouped = out["grouped_skills"]
    assert [s["name"] for s in grouped["Compétences Techniques"]] == ["X", "Y", "Z"]
    assert [s["name"] for s in grouped["Savoir-être"]] == ["Adapt"]


def test_apply_text_overrides_unknown_id_silently_ignored():
    """Un override sur un id inconnu ne doit pas faire crasher ni muter le CV."""
    from engine.cv_generator import PersonalCVGenerator

    gen = PersonalCVGenerator()
    cv_data = {
        "experiences": [{"id": "AM_PFE", "achievements": ["keep"]}],
        "projects": [],
        "grouped_skills": {},
    }
    overrides = {"achievements": {"GHOST": ["x"]}}
    out = gen._apply_text_overrides(cv_data, section_overrides=overrides)
    # Inchangé
    assert out["experiences"][0]["achievements"] == ["keep"]


def test_apply_text_overrides_legacy_compat():
    """headline_override / summary_override (anciens) restent fonctionnels."""
    from engine.cv_generator import PersonalCVGenerator

    gen = PersonalCVGenerator()
    cv_data = {"headline": "h0", "summary": "s0", "experiences": [], "projects": []}
    out = gen._apply_text_overrides(
        cv_data, headline_override="LEGACY_H", summary_override="LEGACY_S"
    )
    assert out["headline"] == "LEGACY_H"
    assert out["summary"] == "LEGACY_S"


def test_apply_text_overrides_section_overrides_win_over_legacy():
    """Si les deux sont fournis, section_overrides gagne (priorité au plus précis)."""
    from engine.cv_generator import PersonalCVGenerator

    gen = PersonalCVGenerator()
    cv_data = {"headline": "h0", "summary": "s0", "experiences": [], "projects": []}
    out = gen._apply_text_overrides(
        cv_data,
        headline_override="LEGACY_H",
        section_overrides={"headline": "PRECISE_H"},
    )
    assert out["headline"] == "PRECISE_H"
