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


def test_build_candidate_context_enriches_with_star_data():
    """Les champs STAR (A, R, S/T) sont enrichis sans modifier les expériences sans STAR."""
    profile_index = {
        "personal_info": {"name": "Zein"},
        "profiles": {
            "simulation_rd": {
                "headline": "Headline",
                "priority_experiences": ["exp-1"],
            }
        },
        "education": [],
    }
    filtered_experiences = [
        {
            "id": "exp-1",
            "A": "Développé un modèle CFD. Conçu une interface Python.",
            "R": "Réduction de 15% du temps de calcul",
            "S": "Contexte industriel R&D",
            "K": ["Python", "CFD"],
        },
        {"id": "exp-2"},  # aucun champ STAR → ne doit pas être modifié
    ]
    context = prompts.build_candidate_context("simulation_rd", profile_index, filtered_experiences, {})

    exp1 = context["experiences"][0]
    assert exp1.get("action_verbs")
    assert "Développé" in exp1["action_verbs"] or "Conçu" in exp1["action_verbs"]
    assert exp1.get("concrete_results") == "Réduction de 15% du temps de calcul"
    assert exp1.get("business_context") == "Contexte industriel R&D"

    # L'expérience sans STAR ne doit pas avoir de champs supplémentaires
    assert context["experiences"][1] == {"id": "exp-2"}

    assert "Développé" in context["detected_action_verbs"] or "Conçu" in context["detected_action_verbs"]
    assert context["profile_priority_ids"] == ["exp-1"]


def test_build_candidate_context_detected_action_verbs_are_sorted_unique():
    profile_index = {
        "personal_info": {},
        "profiles": {"p": {}},
        "education": [],
    }
    exps = [
        {"id": "e1", "A": ["Simulé des modèles", "Analysé les résultats"]},
        {"id": "e2", "A": "Simulé une interface. Validé les tests."},
    ]
    context = prompts.build_candidate_context("p", profile_index, exps, {})
    verbs = context["detected_action_verbs"]
    assert verbs == sorted(set(verbs))  # trié et sans doublons


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


def test_validate_llm_output_marks_fields_for_rewrite():
    """Les champs tronqués doivent apparaître dans fields_to_rewrite avec l'original."""
    very_long = "mot " * 200
    data = {
        "cv": {
            "headline": {"value": very_long},
            "summary": {"value": very_long},
            "experiences": [],
            "projects": [
                {"rewritten_title": "ok", "one_line_description": very_long},
            ],
        }
    }
    result = prompts.validate_llm_output_constraints(data)
    fields_to_rewrite = result.get("fields_to_rewrite", [])
    field_names = [f["field"] for f in fields_to_rewrite]
    assert "headline" in field_names
    assert "summary" in field_names
    assert any("desc" in fn for fn in field_names)
    # L'original doit être conservé pour la réécriture contrôlée
    for entry in fields_to_rewrite:
        assert "original" in entry
        assert "max_chars" in entry


def test_validate_llm_output_constraints_handles_missing_cv():
    result = prompts.validate_llm_output_constraints({})
    assert result["had_violations"] is True
    assert "Missing 'cv' key" in result["violations"]
    assert result["fields_to_rewrite"] == []


def test_post_process_llm_output_keeps_original_words_without_auto_replacement():
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
    assert "Apprenti" in cleaned["headline"]["value"]
    assert "Étudiant" in cleaned["summary"]["value"]
    assert "apprentissage" in cleaned["summary"]["value"].lower()


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
    skills_count = len([s.strip() for s in result["cv_data"]["cv"]["skills_inline"].split("·") if s.strip()])
    assert skills_count >= 6


def test_build_compression_prompt_returns_expected_structure():
    result = prompts.build_compression_prompt("summary", "Texte très long...", 420, min_chars=280)
    assert result["field_name"] == "summary"
    assert result["max_chars"] == 420
    assert result["min_chars"] == 280
    assert "original_text" in result
    assert "Texte très long..." in result["original_text"]
    # Les contraintes doivent mentionner les limites
    constraints_text = " ".join(result["constraints"])
    assert "420" in constraints_text
    assert "280" in constraints_text


def test_build_compression_prompt_without_min():
    result = prompts.build_compression_prompt("headline", "Headline beaucoup trop longue", 90)
    assert result["min_chars"] == 0
    assert result["max_chars"] == 90
    constraints_text = " ".join(result["constraints"])
    assert "90" in constraints_text


# ── Tests qualité perçue ────────────────────────────────────────────────────

def test_assess_output_quality_detects_results_markers():
    cv_data = {
        "cv": {
            "summary": {"value": "Réduction de 30% des délais projet."},
            "experiences": [
                {"bullets": ["Développé un système x2 plus rapide", "Optimisé le code CFD"]},
            ],
        }
    }
    quality = prompts.assess_output_quality(cv_data)
    assert quality["has_results_markers"] is True
    assert quality["lexical_diversity"] > 0
    assert quality["quality_score"] > 0
    assert quality["total_words"] > 0


def test_assess_output_quality_detects_repetitions():
    cv_data = {
        "cv": {
            "experiences": [
                {"bullets": ["Développé module A", "Développé module B", "Développé module C", "Développé module D"]},
            ],
        }
    }
    quality = prompts.assess_output_quality(cv_data)
    # 4 bullets, tous commencent par "développé"
    assert quality["repetition_rate"] == 1.0


def test_assess_output_quality_no_repetitions_diverse_lexicon():
    cv_data = {
        "cv": {
            "experiences": [
                {"bullets": [
                    "Conçu une architecture microservices scalable sous Kubernetes",
                    "Optimisé les requêtes SQL pour réduire la latence de 40%",
                    "Déployé un pipeline CI/CD complet avec GitHub Actions",
                ]}
            ],
            "summary": {"value": "Ingénieur backend expérimenté spécialisé cloud et DevOps."},
        }
    }
    quality = prompts.assess_output_quality(cv_data)
    assert quality["repetition_rate"] == 0.0
    assert quality["has_results_markers"] is True
    assert quality["lexical_diversity"] > 0.5
    assert quality["quality_score"] >= 60


def test_assess_output_quality_empty_cv():
    quality = prompts.assess_output_quality({})
    assert quality["lexical_diversity"] == 0.0
    assert quality["has_results_markers"] is False
    assert quality["repetition_rate"] == 0.0
    assert quality["quality_score"] >= 0
    assert quality["total_words"] == 0


def test_assess_output_quality_accepts_assembled_cv_format():
    """assess_output_quality doit fonctionner sur la sortie de _assemble_final_data (pas de clé 'cv')."""
    cv_direct = {
        "headline": "Ingénieur simulation",
        "summary": "Profil R&D orienté simulation numérique avec 2 ans d'expérience.",
        "experiences": [
            {"achievements": ["Simulé des modèles thermiques sous Abaqus", "Réduit les temps de calcul de 20%"]},
        ],
    }
    quality = prompts.assess_output_quality(cv_direct)
    assert quality["has_results_markers"] is True
    assert quality["lexical_diversity"] > 0
