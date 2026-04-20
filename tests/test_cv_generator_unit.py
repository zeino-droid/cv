import json

import pytest

from engine.cv_generator import PersonalCVGenerator


class _DummyEngine:
    def __init__(self, *args, **kwargs):
        self.model_name = "dummy"
        self.model = "dummy"
        self.available = False

    def is_ready(self):
        return False


@pytest.fixture
def generator(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.cv_generator.GeminiEngine", _DummyEngine)
    monkeypatch.setattr("engine.cv_generator.MLXEngine", _DummyEngine)
    monkeypatch.setattr("engine.cv_generator.OllamaEngine", _DummyEngine)

    profile_path = tmp_path / "master_profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "personal_info": {
                    "name": "Zein",
                    "languages": [{"language": "Français", "level": "Natif"}],
                },
                "profiles": {
                    "simulation_rd": {
                        "headline": "Ingénieur simulation",
                        "summary": "Résumé profil",
                        "target_keywords": ["python", "ansys"],
                    }
                },
                "skills_taxonomy": {
                    "hard_skills": [{"name": "Python"}, {"name": "Ansys"}],
                    "domain_knowledge": ["Thermique"],
                    "soft_skills": ["Communication"],
                },
                "experiences": [],
                "education": [
                    {
                        "degree": "Master",
                        "institution": "UTC",
                        "period": "2025",
                        "specialization": "Simulation",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return PersonalCVGenerator(master_profile_path=str(profile_path))


def test_normalize_job_defaults(generator):
    normalized = generator._normalize_job({})
    assert normalized == {
        "title": "Ingénieur",
        "company": "Entreprise",
        "description": "",
        "url": "",
    }


def test_slugify_normalizes_and_fallbacks(generator):
    assert generator._slugify("Data Engineer @ ACME!") == "data_engineer__acme"
    assert generator._slugify("!!!") == "cv"


def test_rank_experiences_splits_pools_and_applies_limits(generator):
    exps = [
        {"id": "pro-1", "title": "A", "profiles_tags": ["simulation_rd"], "K": ["python"]},
        {"id": "pro-2", "title": "B", "profiles_tags": ["all"], "K": ["ansys"]},
        {"id": "pro-3", "title": "C", "profiles_tags": ["simulation_rd"], "K": []},
        {
            "id": "proj-1",
            "type": "academic_project",
            "title": "P1",
            "profiles_tags": ["simulation_rd"],
            "K": ["python"],
        },
        {
            "id": "proj-2",
            "type": "academic_project",
            "title": "P2",
            "profiles_tags": ["simulation_rd"],
            "K": ["ansys"],
        },
        {
            "id": "proj-3",
            "type": "academic_project",
            "title": "P3",
            "profiles_tags": ["simulation_rd"],
            "K": ["ansys"],
        },
    ]
    ranked = generator.rank_experiences_for_profile(exps, "simulation_rd", ["python", "ansys"])
    assert [e["id"] for e in ranked["pro_experiences"]] == ["pro-1", "pro-3"]
    assert [e["id"] for e in ranked["projects"]] == ["proj-1", "proj-2"]


def test_enforce_project_guarantee_uses_latest_semester(generator):
    ranked = {"pro_experiences": [], "projects": []}
    all_exps = [
        {"id": "p1", "type": "academic_project", "title": "Old", "period": "S8"},
        {"id": "p2", "type": "academic_project", "title": "Recent", "period": "S10"},
    ]
    updated = generator.enforce_project_guarantee(ranked, all_exps)
    assert [p["id"] for p in updated["projects"]] == ["p2"]


def test_assemble_final_data_maps_llm_output_and_falls_back_to_context(generator):
    context = {
        "personal_info": {"name": "Zein", "languages": [{"language": "Français", "level": "Natif"}]},
        "target_profile": {"headline": "Fallback Headline", "summary": "Fallback Summary"},
        "experiences": [
            {
                "id": "exp-1",
                "title": "Ingénieur",
                "company": "ACME",
                "period": "2022 - 2024",
                "location": "Paris",
                "A": ["A1", "A2", "A3"],
            }
        ],
        "ranked_projects": [{"id": "proj-1", "title": "Proj", "D": "Desc", "K": ["Python", "CFD"]}],
        "education": [{"degree": "Master", "institution": "UTC", "period": "2025", "specialization": "Simu"}],
    }
    llm_output = {
        "cv": {
            "headline": {"value": "Headline LLM"},
            "summary": {"value": "Summary LLM"},
            "experiences": [{"id": "exp-1", "rewritten_title": "Senior Engineer", "bullets": ["B1", "B2", "B3"]}],
            "projects": [{"id": "proj-1", "rewritten_title": "Proj LLM", "one_line_description": "Line"}],
            "skills_inline": "Python · CFD",
        }
    }
    data = generator._assemble_final_data(llm_output, context)
    assert data["headline"] == "Headline LLM"
    assert data["summary"] == "Summary LLM"
    assert data["experiences"][0]["position"] == "Senior Engineer"
    assert data["experiences"][0]["achievements"] == ["B1", "B2"]
    assert data["projects"][0]["name"] == "Proj LLM"
    assert data["projects"][0]["keywords"] == "Python · CFD"
    assert data["languages"] == [{"name": "Français", "level": "Natif"}]
