from engine import prompts


def test_build_candidate_context_uses_safe_personal_info():
    profile_index = {
        "personal_info": {
            "name": "Zein",
            "summary_default": "Résumé défaut",
            "secret": {"value": "x", "hidden": True},
        },
        "profiles": {"simulation_rd": {"headline": "Headline cible"}},
        "education": [{"degree": "Master"}],
    }
    context = prompts.build_candidate_context(
        "simulation_rd",
        profile_index,
        filtered_experiences=[{"id": "exp-1"}],
        filtered_skills={"hard_skills": []},
    )
    assert "secret" not in context["personal_info"]
    assert context["target_profile"]["headline"] == "Headline cible"
    assert context["target_profile"]["summary"] == "Résumé défaut"
    assert context["experiences"] == [{"id": "exp-1"}]


def test_validate_llm_output_constraints_limits_and_truncates_fields():
    very_long = "mot " * 200
    many_skills = " · ".join([f"Skill{i}" for i in range(1, 21)])
    data = {
        "cv": {
            "headline": {"value": very_long},
            "summary": {"value": very_long},
            "experiences": [
                {"bullets": [very_long, very_long, "extra"]},
                {"bullets": ["ok"]},
                {"bullets": ["ignored"]},
            ],
            "projects": [
                {"rewritten_title": very_long, "one_line_description": very_long},
                {"rewritten_title": "ok", "one_line_description": "ok"},
                {"rewritten_title": "ignored", "one_line_description": "ignored"},
            ],
            "skills_inline": many_skills,
        }
    }
    result = prompts.validate_llm_output_constraints(data)
    cv = result["cv_data"]["cv"]
    assert result["had_violations"] is True
    assert len(cv["experiences"]) == 3
    assert len(cv["experiences"][0]["bullets"]) == 2
    assert len(cv["projects"]) == 2
    assert len([s.strip() for s in cv["skills_inline"].split("·") if s.strip()]) == 12
    assert cv["headline"]["char_count"] <= 91
    assert cv["summary"]["char_count"] <= 421


def test_validate_llm_output_constraints_handles_missing_cv():
    result = prompts.validate_llm_output_constraints({})
    assert result["had_violations"] is True
    assert "Missing 'cv' key" in result["violations"]


def test_post_process_llm_output_rewrites_forbidden_words():
    raw = {
        "cv": {
            "headline": {"value": "Apprenti simulation"},
            "summary": {"value": "Étudiant passionné en apprentissage"},
            "experiences": [{"bullets": ["élève ingénieur"]}],
            "projects": [],
        }
    }
    result = prompts.post_process_llm_output(raw)
    cleaned = result["cv_data"]["cv"]
    assert "Apprenti" not in cleaned["headline"]["value"]
    assert "Étudiant" not in cleaned["summary"]["value"]
    assert "apprentissage" not in cleaned["summary"]["value"].lower()


def test_validate_llm_output_constraints_flags_under_minimum_fields():
    data = {
        "cv": {
            "headline": {"value": "Titre"},
            "summary": {"value": "Court"},
            "experiences": [{"bullets": ["court"]}],
            "projects": [{"rewritten_title": "P", "one_line_description": "Ligne"}],
            "skills_inline": "Python · CFD",
        }
    }
    result = prompts.validate_llm_output_constraints(data)
    assert result["had_violations"] is True
    actions = {v["action"] for v in result["violations"] if isinstance(v, dict)}
    assert "below_min" in actions
