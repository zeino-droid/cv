import asyncio
import json
import os
import sys
from pathlib import Path

# Adjust path to import engine
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Mock environment if needed
if not os.environ.get("GEMINI_API_KEY"):
    print("⚠️  GEMINI_API_KEY non configurée. Le moteur passera en heuristique.")

from engine.cv_generator import PersonalCVGenerator

async def debug_generation():
    print("🔍 DÉBOGAGE GÉNÉRATION CV V5")
    print("-" * 30)
    
    try:
        generator = PersonalCVGenerator()
        print(f"✅ Moteur chargé : {generator.llm_name}")
        
        # Sample Job
        sample_job = {
            "title": "Ingénieur Simulation R&D",
            "company": "ArcelorMittal R&D",
            "description": "Simulation par éléments finis (Abaqus), modélisation thermique, jumeaux numériques et Python."
        }
        
        print(f"🚀 Génération pour : {sample_job['title']} @ {sample_job['company']}")
        result = await generator.generate_cv_for_job(sample_job)
        
        if "error" in result:
            print(f"❌ Erreur de génération : {result['error']}")
            return

        cv_data = result.get("cv_data", {})
        print("\n📊 RÉSULTAT DU MATCHING (JSON)")
        print(json.dumps(cv_data, indent=2, ensure_ascii=False))
        
        print("\n🧐 VÉRIFICATIONS :")
        # 1. Vérifier la spécialisation ENSEM
        edu = cv_data.get("education", [])
        if edu:
            print(f"   [Formation] {edu[0].get('school')} : {edu[0].get('degree')}")
            print(f"   [Spécialisation] {edu[0].get('specialization')}")
        
        # 2. Vérifier la fusion des entreprises
        exps = cv_data.get("experiences", [])
        print(f"   [Expériences] {len(exps)} selectionnées")
        for e in exps:
            print(f"      - {e.get('position')} @ {e.get('company')}")
            
        print("\n✅ Diagnostic terminé.")
        
    except Exception as e:
        print(f"❌ ÉCHEC DU DIAGNOSTIC : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_generation())
