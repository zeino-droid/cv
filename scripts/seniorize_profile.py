import json
import os
import re
from pathlib import Path
from engine.history import ProfileHistory

def seniorize_content(content):
    if isinstance(content, str):
        # 1. Linguistic Pushing
        content = re.sub(r"\bPFE\b", "Projet de Fin d'Études", content, flags=re.IGNORECASE)
        content = re.sub(r"\bÉlève-ingénieur\b", "Ingénieur", content, flags=re.IGNORECASE)
        content = re.sub(r"\bApprentissage\b", "Parcours Alternance", content, flags=re.IGNORECASE)
        content = re.sub(r"\bAlternance\b", "Parcours Alternance", content, flags=re.IGNORECASE)
        
        # 2. Structural/Academic Cleanup
        # Remove Semester references (S5, S6, etc.)
        content = re.sub(r"\bS[5-9]\b", "", content)
        content = re.sub(r"\bSemestre\s+\d+\b", "Spécialisation", content, flags=re.IGNORECASE)
        content = re.sub(r"\bTP\b", "Pratique Technique", content)
        
        # Cleanup double spaces/trailing punctuation caused by removals
        content = re.sub(r"\s+", " ", content).strip()
        content = content.replace(" ,", ",").replace(" .", ".")
        
        return content
    elif isinstance(content, list):
        return [seniorize_content(item) for item in content]
    elif isinstance(content, dict):
        new_dict = {}
        for k, v in content.items():
            new_dict[k] = seniorize_content(v)
        return new_dict
    return content

def main():
    profile_path = Path("profiles/master_profile.json")
    
    if not profile_path.exists():
        print(f"Error: {profile_path} not found.")
        return

    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    # Use ProfileHistory for Career Versioning
    history_manager = ProfileHistory(profile_path)
    
    # Apply seniorization
    seniorized_profile = seniorize_content(profile)

    # Save with history (this creates snapshot and git commit)
    history_manager.save_with_history(seniorized_profile, message="Seniorization of profile")
    
    print(f"🚀 Profile seniorized and versioned! {profile_path} updated.")

if __name__ == "__main__":
    main()
