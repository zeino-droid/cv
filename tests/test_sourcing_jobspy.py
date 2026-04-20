from engine import sourcing_jobspy


def test_clean_handles_empty_like_values():
    assert sourcing_jobspy._clean("nan") == ""
    assert sourcing_jobspy._clean(" None ") == ""
    assert sourcing_jobspy._clean("valeur") == "valeur"


def test_jobspy_to_standard_returns_none_when_required_fields_missing():
    assert sourcing_jobspy.jobspy_to_standard({"title": "", "company": "ACME"}) is None
    assert sourcing_jobspy.jobspy_to_standard({"title": "Ingénieur", "company": ""}) is None


def test_jobspy_to_standard_maps_fields_with_defaults():
    job = sourcing_jobspy.jobspy_to_standard(
        {
            "title": "Ingénieur R&D",
            "company": "ACME",
            "location": "",
            "job_url": "https://example.com/job",
            "description": "Mission",
            "site": "linkedin",
        }
    )
    assert job is not None
    assert job["location"] == "France"
    assert job["source"] == "linkedin"
    assert job["job_type"] == "CDI"


def test_score_job_applies_skill_bonus_premium_location_and_penalty():
    config = {
        "filters": {"exclude_keywords": ["stage"]},
        "scoring": {
            "base_score": 20,
            "per_skill_match": 10,
            "premium_keywords": {"python": 5},
            "preferred_locations": ["paris"],
            "location_bonus": 7,
            "stage_penalty": -50,
        },
    }
    profile = {
        "skills_taxonomy": {
            "hard_skills": [{"name": "Python"}],
            "domain_knowledge": ["Simulation"],
        }
    }
    job = {
        "title": "Stage ingénieur Python",
        "description": "Simulation avancée avec Python",
        "location": "Paris",
    }
    scored = sourcing_jobspy.score_job(job, profile, config)
    assert scored["fit_score"] == 2
    assert scored["matched_skills"] == ["Python", "Simulation"]


def test_deduplicate_keeps_unique_title_company_pairs():
    jobs = [
        {"title": "Ingénieur R&D", "company": "ACME"},
        {"title": " Ingénieur   R&D ", "company": "acme"},
        {"title": "Data Engineer", "company": "ACME"},
    ]
    unique = sourcing_jobspy.deduplicate(jobs)
    assert len(unique) == 2


def test_scan_all_france_pipeline(monkeypatch):
    monkeypatch.setattr(
        sourcing_jobspy,
        "load_config",
        lambda: {
            "search": {"keywords": ["kw"], "locations": ["Paris"]},
            "filters": {"min_score": 50},
        },
    )
    monkeypatch.setattr(sourcing_jobspy, "load_master_profile", lambda: {"skills_taxonomy": {}})
    monkeypatch.setattr(
        sourcing_jobspy,
        "scan_with_jobspy",
        lambda keywords, locations, progress_callback=None: [
            {"title": "A", "company": "X", "fit_score": 0},
            {"title": "A", "company": "X", "fit_score": 0},
            {"title": "B", "company": "Y", "fit_score": 0},
        ],
    )
    monkeypatch.setattr(
        sourcing_jobspy,
        "score_job",
        lambda job, profile, config: {**job, "fit_score": 60 if job["title"] == "B" else 40},
    )

    progress = []
    results = sourcing_jobspy.scan_all_france(lambda pct, msg: progress.append((pct, msg)))
    assert [j["title"] for j in results] == ["B"]
    assert progress[-1][0] == 1.0
