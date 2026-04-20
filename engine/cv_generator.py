"""
🎯 GÉNÉRATEUR CV HYBRIDE (V4) - ONE-PAGE GUARANTEE
Architecture modulaire avec boucle de correction automatique (Shrink Loop).
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Imports locaux
from engine.engines import GeminiEngine, MLXEngine, OllamaEngine
from engine import matching
from engine import prompts
from engine.rendering import LatexRenderer, MarkdownRenderer, TypstRenderer

DEFAULT_OUTPUT_DIR = Path("vault/resumes")

class PersonalCVGenerator:
    """Orchestrateur central du Cerveau avec garantie One-Page."""

    def __init__(self, master_profile_path: str = "profiles/master_profile.json"):
        self.master_profile_path = Path(master_profile_path)

        if not self.master_profile_path.exists():
            raise FileNotFoundError(f"Profil maître non trouvé à {self.master_profile_path}")

        self.master_profile = matching.load_profile_index(str(self.master_profile_path))

        # Renderers
        self.renderers = {
            "pdf": TypstRenderer(),
            "md": MarkdownRenderer(),
            "tex": LatexRenderer(),
        }

        # LLM Engine selection
        import os
        gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        
        self.gemini = GeminiEngine(api_key=gemini_api_key)
        self.mlx = MLXEngine()
        self.ollama = OllamaEngine()

        if self.gemini.is_ready():
            self.llm = self.gemini
            self.llm_name = f"Gemini Cloud ({self.gemini.model_name})"
        elif self.mlx.available:
            self.llm = self.mlx
            self.llm_name = f"MLX ({self.mlx.model_name.split('/')[-1]})"
        elif self.ollama.is_ready():
            self.llm = self.ollama
            self.llm_name = f"Ollama ({self.ollama.model})"
        else:
            self.llm = None
            self.llm_name = "Heuristique uniquement"

        self._print_status()

    def _print_status(self):
        print(f"\n   {'=' * 40}")
        print(f"   🧠 CERVEAU V4 — ONE-PAGE GUARANTEE")
        print(f"   {'=' * 40}")
        name = self.master_profile.get('personal_info', {}).get('name', 'Inconnu')
        print(f"   👤 Profil: {name}")
        print(f"   🤖 LLM:    {self.llm_name}")
        print(f"   📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}")
        print(f"   {'=' * 40}")

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        """
        Génère un CV avec une boucle de réduction (Shrink Loop) pour garantir 1 page.
        """
        job_data = self._normalize_job(job)
        print(f"\n   📄 GEN ONE-PAGE: {job_data.get('title')} @ {job_data.get('company')}")

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(job_data, self.master_profile)
        print(f"      → Profil cible : {profile_id.upper()} (Score: {match_score})")

        # 2. SHRINK LOOP - 3 niveaux de réduction
        attempts_config = [
            {"max_exp": 3, "font_delta": 0.0},
            {"max_exp": 3, "font_delta": -0.3},
            {"max_exp": 2, "font_delta": -0.5},
        ]

        best_result = None
        slug = self._slugify(f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_base = DEFAULT_OUTPUT_DIR / f"cv_{slug}_{timestamp}"

        for attempt, config in enumerate(attempts_config, 1):
            print(f"      → Tentative {attempt}/{len(attempts_config)} (Max Exp: {config['max_exp']}, Font: {config['font_delta']})")
            
            # Filtrage et limitation des expériences
            filtered_exps = matching.filter_experiences_by_profile(profile_id, self.master_profile)
            # On ne garde que les N meilleures expériences pour l'offre
            # Ici on utilise la liste filtrée par profil, limitée par la config
            limited_exps = filtered_exps[:config["max_exp"]]
            
            filtered_skills = matching.filter_skills_by_profile(profile_id, self.master_profile)
            
            # Construction du contexte et du prompt
            candidate_context = prompts.build_candidate_context(profile_id, self.master_profile, limited_exps, filtered_skills)
            
            cv_data = {}
            if self.llm:
                prompt_dict = prompts.build_generation_prompt(job_data, candidate_context, profile_id)
                prompt_str = json.dumps(prompt_dict, ensure_ascii=False, indent=2)
                response_str = await self.llm.generate(prompt_str)
                
                try:
                    clean_json = re.sub(r"```json\s*|\s*```", "", response_str).strip()
                    llm_output = json.loads(clean_json)
                    
                    # Post-processing (inclut la validation One-Page Couche 1)
                    validation_result = prompts.post_process_llm_output(llm_output)
                    cv_data = self._assemble_final_data(validation_result["cv_data"], candidate_context)
                except Exception as e:
                    print(f"      ⚠️ Erreur parsing LLM: {e}. Fallback.")
                    cv_data = self._assemble_fallback_data(candidate_context, job_data)
            else:
                cv_data = self._assemble_fallback_data(candidate_context, job_data)

            # Rendu PDF pour vérification
            results = {}
            pdf_renderer = self.renderers["pdf"]
            pdf_path = pdf_renderer.render(cv_data, output_base, font_size_delta=config["font_delta"])
            
            if pdf_path:
                page_count = pdf_renderer.get_page_count(pdf_path)
                print(f"      → Pages: {page_count}")
                
                results["pdf_path"] = str(pdf_path)
                results["page_count"] = page_count
                results["cv_data"] = cv_data
                
                if page_count == 1:
                    # Succès immédiat ! On génère les autres formats
                    for fmt in ["md", "tex"]:
                        p = self.renderers[fmt].render(cv_data, output_base)
                        if p: results[f"{fmt}_path"] = str(p)
                    return results
                
                best_result = results # On garde la dernière tentative au cas où
            else:
                print("      ⚠️ Échec du rendu PDF.")

        # Si on arrive ici, on n'a pas réussi à faire 1 page ou on a épuisé les tentatives
        print("      ⚠️ Garantie One-Page non atteinte après toutes les tentatives.")
        return best_result or {"error": "Génération échouée"}

    def _assemble_final_data(self, llm_output: Dict, context: Dict) -> Dict:
        """Assemble les données générées par l'IA avec les infos de base."""
        cv_gen = llm_output.get("cv", {})
        
        final_exps = []
        gen_exps = {exp["id"]: exp for exp in cv_gen.get("experiences", [])}
        
        for exp in context["experiences"]:
            exp_id = exp.get("id")
            if exp_id in gen_exps:
                gen_exp = gen_exps[exp_id]
                final_exps.append({
                    "position": gen_exp.get("rewritten_title", exp.get("title")),
                    "company": exp.get("company"),
                    "start_date": exp.get("period", "").split("-")[0].strip(),
                    "end_date": exp.get("period", "").split("-")[-1].strip() if "-" in exp.get("period", "") else "",
                    "location": exp.get("location", ""),
                    "achievements": gen_exp.get("bullets", exp.get("A", []))
                })
            else:
                final_exps.append({
                    "position": exp.get("title"),
                    "company": exp.get("company"),
                    "start_date": exp.get("period", ""),
                    "end_date": "",
                    "achievements": [exp.get("A", "")] if isinstance(exp.get("A"), str) else exp.get("A", [])
                })

        # Formattage skills
        skills_inline = cv_gen.get("skills_inline", "")
        if skills_inline:
            grouped_skills = {"Compétences": [{"name": s.strip()} for s in skills_inline.split("·")]}
        else:
            grouped_skills = {
                "Hard Skills": [{"name": s["name"]} for s in context["skills"]["hard_skills"][:8]],
                "Domaines": [{"name": s} for s in context["skills"]["domain_knowledge"][:6]]
            }

        return {
            "identity": context["personal_info"],
            "headline": cv_gen.get("headline", {}).get("value", context["target_profile"]["headline"]),
            "summary": cv_gen.get("summary", {}).get("value", context["target_profile"]["summary"]),
            "experiences": final_exps,
            "grouped_skills": grouped_skills,
            "education": [
                {
                    "degree": edu.get("degree"),
                    "school": edu.get("institution"),
                    "year": edu.get("period"),
                    "details": edu.get("specialization", "")
                } for edu in context["education"]
            ][:2], # Max 2 formations pour l'espace
            "languages": [
                {"name": l["language"], "level": l["level"]} for l in context["personal_info"].get("languages", [])
            ],
            "projects": []
        }

    def _assemble_fallback_data(self, context: Dict, job: Dict) -> Dict:
        return self._assemble_final_data({"cv": {}}, context)

    def _normalize_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": str(job.get("title", "Ingénieur")).strip(),
            "company": str(job.get("company", "Entreprise")).strip(),
            "description": str(job.get("description", "")).strip(),
            "url": job.get("url", "")
        }

    def _slugify(self, value: str) -> str:
        slug = value.lower().replace(" ", "_")
        slug = re.sub(r"[^a-z0-9_]", "", slug)
        return slug or "cv"
