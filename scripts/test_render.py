#!/usr/bin/env python3
"""
🧪 Automated "Aesthetic" Regression Testing
Renders sample CVs and detects layout shifts using visual comparison.
"""

import sys
import os
import json
import shutil
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from engine.cv_generator import PersonalCVGenerator
from engine.rendering import TypstRenderer
import pypdfium2 as pdfium
from PIL import Image, ImageChops, ImageStat

# Config
BASELINE_DIR = PROJECT_ROOT / "tests" / "baselines"
CURRENT_DIR = PROJECT_ROOT / "tests" / "current"
DIFF_DIR = PROJECT_ROOT / "tests" / "diffs"
NUM_TEST_CASES = 50
THRESHOLD = 0.001 # 0.1% change threshold

def generate_mock_jobs() -> List[Dict[str, Any]]:
    """Generates 50 varied job descriptions for testing."""
    titles = [
        "Ingénieur Simulation Numérique",
        "Ingénieur Calcul FEA",
        "Data Scientist R&D",
        "Ingénieur d'Études",
        "Ingénieur Procédés",
        "Chef de Projet Technique",
        "Ingénieur Mécanique des Fluides",
        "Ingénieur Thermique",
        "Expert Simulation Multi-physique",
        "Ingénieur Junior Simulation"
    ]
    
    keywords_sets = [
        ["Abaqus", "Python", "Optimisation"],
        ["CFD", "Ansys", "Thermique"],
        ["Matlab", "Simulink", "Automatique"],
        ["SolidWorks", "Calcul de structure", "Eurocodes"],
        ["Scikit-learn", "Pandas", "Machine Learning"],
        ["Projets", "Management", "Agile"],
        ["Recherche", "Innovation", "Matériaux"],
        ["Modélisation", "C++", "Algorithmique"],
        ["Industrie 4.0", "Digital Twin", "IoT"],
        ["Énergie", "Hydrogène", "Transition Énergétique"]
    ]
    
    companies = ["Airbus", "TotalEnergies", "ArcelorMittal", "Renault", "Dassault Systèmes", "Alstom", "EDF", "Safran", "Thales", "Suez"]
    
    jobs = []
    for i in range(NUM_TEST_CASES):
        title = titles[i % len(titles)]
        kw = keywords_sets[i % len(keywords_sets)]
        company = companies[i % len(companies)]
        
        # Vary the description length to test layout adaptivity
        desc = f"Nous recherchons un {title} pour rejoindre notre équipe à {company}. "
        desc += "Compétences clés : " + ", ".join(kw) + ". "
        if i % 3 == 0:
            desc += "Expérience en environnement industriel exigeant. Capacité à travailler en équipe et à résoudre des problèmes complexes."
        if i % 5 == 0:
            desc += " Maîtrise avancée de la simulation numérique et de l'analyse de données."
        
        jobs.append({
            "id": f"test_{i:02d}",
            "title": title,
            "company": company,
            "description": desc
        })
    return jobs

def pdf_to_png(pdf_path: Path, png_path: Path):
    """Converts the first page of a PDF to a PNG image."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[0]
    bitmap = page.render(scale=2) # 144 DPI (72 * 2)
    pil_image = bitmap.to_pil()
    pil_image.save(png_path)

def compare_visuals(current_png: Path, baseline_png: Path, diff_png: Path) -> float:
    """Compares two images and returns a shift score (0.0 to 1.0)."""
    if not baseline_png.exists():
        return -1.0
    
    img_c = Image.open(current_png).convert("RGB")
    img_b = Image.open(baseline_png).convert("RGB")
    
    if img_c.size != img_b.size:
        return 1.0 # Significant layout shift (size change)
    
    diff = ImageChops.difference(img_c, img_b)
    if diff.getbbox():
        diff.save(diff_png)
        stat = ImageStat.Stat(diff)
        # Shift score is the average pixel difference normalized
        score = sum(stat.sum) / (img_c.size[0] * img_c.size[1] * 3 * 255)
        return score
    return 0.0

async def run_tests():
    print(f"🚀 Starting Aesthetic Regression Testing ({NUM_TEST_CASES} cases)...")
    
    # Cleanup current and diffs
    for d in [CURRENT_DIR, DIFF_DIR]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    
    generator = PersonalCVGenerator()
    jobs = generate_mock_jobs()
    
    results = []
    
    for i, job in enumerate(jobs):
        test_id = job["id"]
        print(f"[{i+1}/{NUM_TEST_CASES}] Testing {test_id}: {job['title']} @ {job['company']}...", end="\r")
        
        # 1. Generate CV Data (Fallback mode for speed and stability)
        # We use internal methods to bypass LLM
        profile_id, _ = generator.master_profile.get("profiles", {}), "simulation_rd" # Default
        from engine import matching, prompts
        profile_id, _ = matching.select_best_profile(job, generator.master_profile)
        
        all_exps = generator.master_profile.get("experience_stark") or generator.master_profile.get("experiences", [])
        job_keywords = [] # Not using extraction for simplicity here
        ranked = generator.rank_experiences_for_profile(all_exps, profile_id, job_keywords, job["description"])
        ranked = generator.enforce_project_guarantee(ranked, all_exps, profile_id)
        
        # Test with attempt 1 configuration (standard)
        config = {
            "max_pro_exp": 4,
            "max_projects": 2,
            "max_bullets": 2,
            "max_education": 2,
            "font_size": 10.4,
            "leading": 0.65,
            "section_gap": 16,
            "margin_sides": 18,
        }
        
        current_pro = ranked["pro_experiences"][:config["max_pro_exp"]]
        current_proj = ranked["projects"][:config["max_projects"]]
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
        cv_data = generator._assemble_fallback_data(context, job, max_bullets=config["max_bullets"])
        
        # 2. Render
        output_base = CURRENT_DIR / test_id
        renderer = TypstRenderer()
        pdf_path = renderer.render(
            cv_data,
            output_base,
            font_size_delta=config["font_size"] - 9.5, # Base is 9.5
            leading=config["leading"],
            section_gap=config["section_gap"],
            margin_sides=config["margin_sides"],
        )
        
        if not pdf_path or not pdf_path.exists():
            results.append({"id": test_id, "status": "FAIL (Render Error)", "score": 1.0})
            continue
            
        # 3. Convert to Image
        png_path = CURRENT_DIR / f"{test_id}.png"
        pdf_to_png(pdf_path, png_path)
        
        # 4. Compare
        baseline_png = BASELINE_DIR / f"{test_id}.png"
        diff_png = DIFF_DIR / f"{test_id}_diff.png"
        
        score = compare_visuals(png_path, baseline_png, diff_png)
        
        status = "OK"
        if score == -1.0:
            status = "NEW"
        elif score > THRESHOLD:
            status = "SHIFT"
        
        results.append({
            "id": test_id,
            "title": job["title"],
            "status": status,
            "score": score
        })

    print("\n\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    shifted = 0
    new = 0
    failed = 0
    
    for r in results:
        indicator = "✅"
        if r["status"] == "SHIFT":
            indicator = "⚠️ "
            shifted += 1
        elif r["status"] == "NEW":
            indicator = "🆕"
            new += 1
        elif "FAIL" in r["status"]:
            indicator = "❌"
            failed += 1
        else:
            passed += 1
        
        score_str = f"{r['score']*100:.3f}%" if r['score'] >= 0 else "N/A"
        print(f"{indicator} {r['id']}: {r['status']:<15} (Shift: {score_str}) | {r['title']}")
    
    print("="*50)
    print(f"TOTAL: {len(results)} | PASSED: {passed} | SHIFTED: {shifted} | NEW: {new} | FAILED: {failed}")
    print("="*50)
    
    if new > 0:
        print(f"\n💡 {new} new tests found. To set them as baseline, run:")
        print(f"cp {CURRENT_DIR}/*.png {BASELINE_DIR}/")
    
    if shifted > 0:
        print(f"\n🚨 {shifted} layout shifts detected! Check {DIFF_DIR} for visual diffs.")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests())
