import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine import matching, prompts
from engine.cv_generator import PersonalCVGenerator
from engine.rendering import TypstRenderer


def build_cv_data() -> dict:
    generator = PersonalCVGenerator()
    job = {
        "title": "Ingénieur Simulation",
        "company": "Test",
        "description": (
            "Simulation numérique CFD énergie python optimisation "
            "procédés industriels performance thermique."
        ),
    }
    profile_id, _ = matching.select_best_profile(job, generator.master_profile)
    all_exps = generator.master_profile.get(
        "experience_stark"
    ) or generator.master_profile.get("experiences", [])
    ranked = generator.rank_experiences_for_profile(all_exps, profile_id, [])
    ranked = generator.enforce_project_guarantee(ranked, all_exps, profile_id)

    current_pro = ranked["pro_experiences"][:4]
    current_proj = ranked["projects"][:2]
    filtered_skills = matching.filter_skills_by_profile(
        profile_id,
        generator.master_profile,
        selected_experiences=current_pro + current_proj,
    )
    context = prompts.build_candidate_context(
        profile_id,
        generator.master_profile,
        current_pro,
        filtered_skills,
    )
    context["ranked_projects"] = current_proj
    return generator._assemble_fallback_data(context, job, max_bullets=3)


def main() -> None:
    renderer = TypstRenderer()
    if not renderer.available:
        print("Typst indisponible: impossible de lancer le test shrink.")
        return

    cv_data = build_cv_data()
    base_dir = Path("vault/resumes")
    base_dir.mkdir(parents=True, exist_ok=True)

    configs = [
        {
            "label": "loose",
            "font_size_delta": 0.0,
            "leading": 0.55,
            "section_gap": 5.0,
            "margin_sides": 14.0,
        },
        {
            "label": "tight",
            "font_size_delta": -0.5,
            "leading": 0.47,
            "section_gap": 3.0,
            "margin_sides": 12.0,
        },
    ]

    for cfg in configs:
        output_base = base_dir / f"test_shrink_{cfg['label']}"
        pdf = renderer.render(
            cv_data,
            output_base,
            font_size_delta=cfg["font_size_delta"],
            leading=cfg["leading"],
            section_gap=cfg["section_gap"],
            margin_sides=cfg["margin_sides"],
        )
        if pdf and pdf.exists():
            pages = renderer.get_page_count(pdf)
            print(f"[{cfg['label']}] → {pdf} | Pages: {pages}")
        else:
            print(f"[{cfg['label']}] → ÉCHEC rendu PDF")


if __name__ == "__main__":
    main()
