import sys
import os
import asyncio
from pathlib import Path

# Add the project root to sys.path to allow importing from core
sys.path.append(os.getcwd())

from engine.cv_generator import PersonalCVGenerator

async def test_brain_integrity():
    """
    Test minimal pour s'assurer que le 'Cerveau' fonctionne toujours.
    Ce test valide que la pipeline de génération produit les 3 formats attendus.
    """
    print("🔍 Vérification de l'intégrité du Cerveau...")
    
    try:
        # 1. Initialisation
        generator = PersonalCVGenerator()
        
        # 2. Mock Job Offer
        mock_job = {
            "title": "Ingénieur R&D Test",
            "company": "Integrity Check Corp",
            "required_skills": ["Python", "Simulation", "Abaqus"],
            "description": "Poste de test pour vérifier que le cerveau ne bug pas."
        }
        
        # 3. Génération (Optionnellement en mode rapide sans LLM si on veut juste tester la forme)
        # Mais ici on teste la vraie pipeline
        print("🛠️ Génération d'un CV de test...")
        result = await generator.generate_cv_for_job(mock_job)
        
        # 4. Validations
        errors = []
        if not result.get("markdown"): errors.append("Manque Markdown")
        if not result.get("latex"): errors.append("Manque LaTeX")
        if not result.get("cv_data"): errors.append("Manque Données JSON")
        
        if errors:
            print(f"❌ ÉCHEC : {', '.join(errors)}")
            sys.exit(1)
            
        print("✅ Intégrité validée : Le cerveau produit du Markdown, du LaTeX et transforme le JSON.")
        
    except Exception as e:
        print(f"💥 CRASH DU CERVEAU : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_brain_integrity())
