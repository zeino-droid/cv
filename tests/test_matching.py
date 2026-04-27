from engine import matching


def test_get_safe_personal_info_removes_hidden_and_non_prompt_fields():
    personal_info = {
        "name": "Zein",
        "email": "z@example.com",
        "secret": {"value": "x", "hidden": True},
        "private": {"value": "y", "inject_in_prompt": False},
    }
    safe = matching.get_safe_personal_info(personal_info)
    assert safe == {"name": "Zein", "email": "z@example.com"}


def test_extract_job_keywords_is_case_insensitive():
    found = matching.extract_job_keywords("Python et simulation thermique", ["python", "CFD", "SIMULATION"])
    assert found == ["python", "SIMULATION"]


def test_select_best_profile_returns_best_match_and_fallback():
    profile_index = {
        "profiles": {
            "simulation_rd": {"target_keywords": ["simulation", "python"]},
            "energy": {"target_keywords": ["energy", "grid"]},
        }
    }
    best, score = matching.select_best_profile({"title": "R&D", "description": "Python simulation"}, profile_index)
    assert (best, score) == ("simulation_rd", 2.0)

    fallback = matching.select_best_profile({"title": "X", "description": "sans mots-clés"}, profile_index)
    assert fallback == ("simulation_rd", 0.0)


def test_filter_experiences_by_profile_honors_priority_and_limit():
    profile_index = {
        "profiles": {"simulation_rd": {"priority_experiences": ["exp-prio"]}},
        "experience_stark": [
            {"id": "exp-1", "profiles_tags": ["all"]},
            {"id": "exp-prio", "profiles_tags": []},
            {"id": "exp-2", "profiles_tags": ["simulation_rd"]},
        ],
    }
    filtered = matching.filter_experiences_by_profile("simulation_rd", profile_index, max_experiences=2)
    assert [exp["id"] for exp in filtered] == ["exp-prio", "exp-1"]


def test_filter_skills_by_profile_prioritizes_keyword_related_skills():
    profile_index = {
        "profiles": {"simulation_rd": {"target_keywords": ["python", "ansys"]}},
        "skills_taxonomy": {
            "hard_skills": [{"name": "CATIA"}, {"name": "Python"}, {"name": "Ansys Fluent"}],
            "domain_knowledge": ["CFD"],
            "soft_skills": ["Leadership"],
        },
    }
    skills = matching.filter_skills_by_profile("simulation_rd", profile_index)
    assert [s["name"] for s in skills["hard_skills"]][:2] == ["Python", "Ansys Fluent"]
    assert skills["domain_knowledge"] == ["CFD"]
    assert skills["soft_skills"] == ["Leadership"]


def test_filter_skills_by_profile_applies_minimum_floor():
    profile_index = {
        "profiles": {"simulation_rd": {"target_keywords": ["abaqus"]}},
        "skills_taxonomy": {
            "hard_skills": [{"name": f"S{i}"} for i in range(1, 9)],
            "domain_knowledge": [],
            "soft_skills": [],
        },
    }
    skills = matching.filter_skills_by_profile("simulation_rd", profile_index)
    assert len(skills["hard_skills"]) >= 6


def test_filter_skills_by_profile_keeps_transversal_skills_even_when_budget_is_tight():
    profile_index = {
        "profiles": {
            "simulation_rd": {
                "target_keywords": [f"stack{i}" for i in range(1, 13)],
            }
        },
        "skills_taxonomy": {
            "hard_skills": (
                [{"name": f"Stack{i}", "level": "avancé"} for i in range(1, 13)]
                + [{"name": "Git", "level": "intermédiaire"}]
            ),
            "domain_knowledge": [],
            "soft_skills": [],
        },
    }
    skills = matching.filter_skills_by_profile("simulation_rd", profile_index)
    selected_names = [s["name"] for s in skills["hard_skills"]]
    assert len(selected_names) == 12
    assert "Git" in selected_names
