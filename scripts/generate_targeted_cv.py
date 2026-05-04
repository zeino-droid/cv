import json
from pathlib import Path

# Lecture du profil maitre
master_path = Path("profiles/master_profile.json")
with open(master_path, "r", encoding="utf-8") as f:
    master = json.load(f)

# Création du CV ciblé
targeted_cv = {
    "identity": master["personal_info"],
    "headline": "Ingénieur Calculs Mécaniques & FEA — Défense & Nucléaire",
    "summary": "Élève-ingénieur généraliste à l'ENSEM spécialisé en mécanique et simulation numérique, en apprentissage chez ArcelorMittal R&D. Expérience avancée en calculs statiques et dynamiques non-linéaires (Abaqus, Metafor) appliqués à la stabilité des structures complexes. Solides compétences en éléments finis (FEA), RDM et rédaction de dossiers justificatifs. Habitué aux revues techniques rigoureuses (QCD) et à l'amélioration continue des méthodes de calcul industriel.",
    "experiences": [
        {
            "id": "AM_PFE",
            "position": "Ingénieur R&D Calculs de Stabilité (PFE)",
            "company": "ArcelorMittal R&D",
            "start_date": "Avril 2026",
            "end_date": "Août 2026",
            "location": "France",
            "achievements": [
                "Pilotage d'études FEA non-linéaires (Abaqus/Explicit, Metafor) pour prédire le flambage dynamique et les instabilités de structures sous contraintes.",
                "Étude de convergence de maillage sur éléments coques et solides, et validation de modèles de calcul statiques et dynamiques.",
                "Établissement de dossiers justificatifs techniques rigoureux et présentation des résultats lors de revues d'experts R&D."
            ]
        },
        {
            "id": "ENSEM_PROJ_COMPOSITES",
            "position": "Projet de Calcul Thermomécanique et FEA",
            "company": "ENSEM Nancy",
            "start_date": "2025",
            "end_date": "2026",
            "location": "Nancy",
            "achievements": [
                "Modélisation éléments finis (Abaqus/CAE) du comportement thermomécanique de structures stratifiées sous chargement complexe.",
                "Analyse des contraintes résiduelles (RDM) et validation croisée des calculs numériques par la Théorie Classique des Stratifiés (CLT)."
            ]
        },
        {
            "id": "AM_A1",
            "position": "Ingénieur Simulation Thermique",
            "company": "ArcelorMittal R&D",
            "start_date": "2023",
            "end_date": "2024",
            "location": "France",
            "achievements": [
                "Développement d'outils de calcul (Python) pour la simulation de transferts thermiques et l'amélioration des méthodes de dimensionnement.",
                "Conduite d'études comparant les modèles théoriques aux données expérimentales, avec respect des contraintes de Qualité, Coût, Délai (QCD)."
            ]
        }
    ],
    "projects": [
        {
            "id": "ENSEM_PROJ_FLUENT",
            "name": "Analyse Multi-Physique sous Environnement Ansys",
            "description": "Validation numérique de profils sous Ansys, incluant gestion avancée du maillage et des solveurs.",
            "keywords": "Ansys · Maillage Structuré · Simulation · Validation"
        }
    ],
    "grouped_skills": {
        "Compétences Techniques": [
            {"name": "Abaqus / Abaqus CAE"},
            {"name": "Ansys Workbench / Apdl"},
            {"name": "Analyse FEA"},
            {"name": "Calculs Statiques & Dynamiques"},
            {"name": "Non-linéaire & Flambage"},
            {"name": "RDM"}
        ],
        "Connaissances Métier": [
            {"name": "Ingénierie Mécanique"},
            {"name": "Normes FEM & 13001"},
            {"name": "Dossiers Justificatifs"},
            {"name": "Gestion de Projet (QCD)"}
        ],
        "Savoir-être": [
            {"name": "Rigueur Scientifique"},
            {"name": "Autonomie"},
            {"name": "Travail en Équipe"},
            {"name": "Relationnel Client"}
        ]
    },
    "education": [
        {
            "degree": "Diplôme d'Ingénieur Mécanique & Systèmes",
            "school": "ENSEM — Groupe INP Lorraine",
            "year": "2023 - 2026",
            "specialization": "Calcul de Structures et Simulation Numérique",
            "details": "Mécanique des Milieux Continus, Dynamique des solides et structures, Flambement, Analyse Numérique.",
            "modules": {
                "Majeure": [
                    "Dynamique des solides (vibrations, flambement)",
                    "Mécanique des Milieux Continus (MMC)",
                    "Analyse numérique & méthodes EDP",
                    "Science des matériaux (rupture, plasticité)"
                ]
            }
        }
    ],
    "languages": [
        {"name": "Anglais", "level": "B2+ (TOEIC 860)"},
        {"name": "Français", "level": "Courant"}
    ],
    "hobbies": master["personal_info"].get("hobbies", [])
}

with open("vault/resumes/CV_CIMEM_TARGETED.json", "w", encoding="utf-8") as f:
    json.dump(targeted_cv, f, ensure_ascii=False, indent=2)

print("CV ciblé créé avec succès.")
