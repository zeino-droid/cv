import json
import os
import re

# List of student-like terms to flag
FORBIDDEN_TERMS = [
    r"apprenti",
    r"étudiant",
    r"etudiant",
    r"stagiaire",
    r"stage",
    r"alternant",
    r"alternance",
    r"élève",
    r"eleve",
    r"pfe",
    r"projet de fin d'études",
    r"projet de fin d'etudes",
    r"travaux pratiques",
    r"tp\s+",
    r"semestre",
    r"cursus",
    r"academic_project",
    r"écol[e]",
    r"université",
    r"universite",
    r"formation",
    r"junior",
    r"s[5-9]",
    r"master\s*[1-2]",
    r"m[1-2]\s+",
    r"bac\s*\+",
    r"iut",
    r"bts",
    r"dut",
    r"cpge",
    r"prépa",
    r"licence",
    r"bachelor",
    r"rapport de stage",
    r"projet tutoré"
]

def scan_dict(d, path=""):
    findings = []
    if isinstance(d, dict):
        for k, v in d.items():
            findings.extend(scan_dict(v, f"{path}.{k}" if path else k))
    elif isinstance(d, list):
        for i, item in enumerate(d):
            findings.extend(scan_dict(item, f"{path}[{i}]"))
    elif isinstance(d, str):
        for term in FORBIDDEN_TERMS:
            if re.search(term, d, re.IGNORECASE):
                findings.append({
                    "path": path,
                    "term": term,
                    "content": d
                })
    return findings

def main():
    profile_path = "profiles/master_profile.json"
    if not os.path.exists(profile_path):
        print(f"Error: {profile_path} not found.")
        return

    with open(profile_path, "r", encoding="utf-8") as f:
        try:
            profile = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return

    print(f"--- Seniority Audit: {profile_path} ---")
    findings = scan_dict(profile)
    
    if not findings:
        print("✅ No student-like terms found. Profile looks senior!")
    else:
        print(f"🚩 Found {len(findings)} potential student-like terms:\n")
        
        # Group by path for better readability
        current_path = ""
        for f in findings:
            if f['path'] != current_path:
                print(f"\n📍 {f['path']}:")
                current_path = f['path']
            print(f"  - [{f['term']}] -> \"{f['content'][:100]}...\"")
            
    print("\n--- End of Audit ---")

if __name__ == "__main__":
    main()
