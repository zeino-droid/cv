import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.cv_generator import PersonalCVGenerator
from engine.matching import filter_skills_by_profile


def run_diagnostic(
    json_path: str = "profiles/master_profile.json",
    profile_id: str = "simulation_rd",
    mock_desc: str = "Ingénieur simulation Abaqus éléments finis flambage Python",
) -> None:
    with open(json_path, encoding="utf-8") as f:
        profile_index = json.load(f)

    generator = PersonalCVGenerator(master_profile_path=json_path)
    all_experiences = profile_index.get("experience_stark") or profile_index.get("experiences", [])
    ranked = generator.rank_experiences_for_profile(
        all_experiences, profile_id, mock_desc.split()
    )
    skills = filter_skills_by_profile(profile_id, profile_index)

    r = ranked.get("fill_report", {})
    l = skills.get("fill_layers", {})
    print(
        f"Exp pro : {r.get('pro_count', 0)}/4 | "
        f"Projets : {r.get('project_count', 0)}/2 | "
        f"Skills : {l.get('skills_total', 0)}/12"
    )
    print(f"IDs pro : {r.get('pro_ids_selected', [])}")
    print(f"Backfill activé : {r.get('floor_activated', False)}")
    print(
        "Couches : "
        f"L1={l.get('layer_1_signature', 0)} "
        f"L2={l.get('layer_2_transversal', 0)}"
    )
    print(f"Hard skills : {[s.get('name') for s in skills.get('hard_skills', [])]}")

    ok = (
        r.get("pro_count", 0) >= 2
        and r.get("project_count", 0) >= 1
        and l.get("skills_total", 0) >= 6
    )
    print("\n✅ PIPELINE OK" if ok else "\n❌ PIPELINE KO — vérifier profiles_tags dans JSON")


if __name__ == "__main__":
    run_diagnostic(profile_id=sys.argv[1] if len(sys.argv) > 1 else "simulation_rd")
