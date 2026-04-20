"""
🎯 GÉNÉRATEUR CV HYBRIDE (V3) - REFACTORISÉ
Architecture modulaire: Matching + LLM + Rendering (Typst)
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
    """Orchestrateur central du Cerveau"""

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
        print(f"   🧠 CERVEAU V3 — STATUS")
        print(f"   {'=' * 40}")
        name = self.master_profile.get('personal_info', {}).get('name', 'Inconnu')
        print(f"   👤 Profil: {name}")
        print(f"   🤖 LLM:    {self.llm_name}")
        print(f"   📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}")
        print(f"   {'=' * 40}")

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        """Génère un CV complet pour une offre spécifique."""
        job_data = self._normalize_job(job)
        print(f"\n   📄 GEN RAPIDE: {job_data.get('title')} @ {job_data.get('company')}")

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(job_data, self.master_profile)
        print(f"      → Profil cible : {profile_id.upper()} (Score: {match_score})")

        # 2. Filtrage des données
        filtered_exps = matching.filter_experiences_by_profile(profile_id, self.master_profile)
        filtered_skills = matching.filter_skills_by_profile(profile_id, self.master_profile)
        
        # 3. Construction du contexte et du prompt
        candidate_context = prompts.build_candidate_context(profile_id, self.master_profile, filtered_exps, filtered_skills)
        
        if self.llm:
            print(f"      → Génération IA...")
            prompt_dict = prompts.build_generation_prompt(job_data, candidate_context, profile_id)
            # On convertit le dict en string pour le LLM
            prompt_str = json.dumps(prompt_dict, ensure_ascii=False, indent=2)
            response_str = await self.llm.generate(prompt_str)
            
            try:
                # Tentative de parser la réponse JSON du LLM
                # On nettoie si le LLM a mis des backticks ```json ... ```
                clean_json = re.sub(r"```json\s*|\s*```", "", response_str).strip()
                llm_output = json.loads(clean_json)
                
                # Post-processing
                llm_output = prompts.post_process_llm_output(llm_output)
                
                # Assemblage final
                cv_data = self._assemble_final_data(llm_output, candidate_context)
            except Exception as e:
                print(f"      ⚠️ Erreur parsing LLM: {e}. Utilisation fallback.")
                cv_data = self._assemble_fallback_data(candidate_context, job_data)
        else:
            cv_data = self._assemble_fallback_data(candidate_context, job_data)

        # 4. Rendu
        slug = self._slugify(f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_base = DEFAULT_OUTPUT_DIR / f"cv_{slug}_{timestamp}"

        results = {}
        for fmt, renderer in self.renderers.items():
            path = renderer.render(cv_data, output_base)
            if path:
                path_str = str(path)
                results[f"{fmt}_path"] = path_str
                if fmt == "md":
                    results["markdown"] = path_str
                elif fmt == "tex":
                    results["latex"] = path_str
                elif fmt == "pdf":
                    results["pdf"] = path_str

        return {"cv_data": cv_data, **results}

    def _assemble_final_data(self, llm_output: Dict, context: Dict) -> Dict:
        """Assemble les données générées par l'IA avec les infos de base."""
        cv_gen = llm_output.get("cv", {})
        
        # Mapping experiences pour garder les dates et infos non générées
        final_exps = []
        gen_exps = {exp["id"]: exp for exp in cv_gen.get("experiences", [])}
        
        for exp in context["experiences"]:
            exp_id = exp.get("id")
            if exp_id in gen_exps:
                gen_exp = gen_exps[exp_id]
                final_exps.append({
                    "position": gen_exp.get("title", exp.get("title")),
                    "company": exp.get("company"),
                    "start_date": exp.get("period", "").split("-")[0].strip(),
                    "end_date": exp.get("period", "").split("-")[-1].strip() if "-" in exp.get("period", "") else "",
                    "location": exp.get("location", ""),
                    "achievements": gen_exp.get("bullet_points", exp.get("A", []))
                })
            else:
                # Fallback pour cette exp
                final_exps.append({
                    "position": exp.get("title"),
                    "company": exp.get("company"),
                    "start_date": exp.get("period", ""),
                    "end_date": "",
                    "achievements": [exp.get("A", "")] if isinstance(exp.get("A"), str) else exp.get("A", [])
                })

        # Formattage skills pour le template Typst
        grouped_skills = {
            "Hard Skills": [{"name": s["name"]} for s in context["skills"]["hard_skills"][:8]],
            "Domaines": [{"name": s} for s in context["skills"]["domain_knowledge"][:6]]
        }

        return {
            "identity": context["personal_info"],
            "headline": cv_gen.get("headline", context["target_profile"]["headline"]),
            "summary": cv_gen.get("summary", context["target_profile"]["summary"]),
            "experiences": final_exps,
            "grouped_skills": grouped_skills,
            "education": [
                {
                    "degree": edu.get("degree"),
                    "school": edu.get("institution"),
                    "year": edu.get("period"),
                    "details": edu.get("specialization", "")
                } for edu in context["education"]
            ],
            "languages": [
                {"name": l["language"], "level": l["level"]} for l in context["personal_info"].get("languages", [])
            ],
            "projects": [] # On peut ajouter les projets si besoin
        }

    def _assemble_fallback_data(self, context: Dict, job: Dict) -> Dict:
        """Version sans IA."""
        # Simplification pour le fallback
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
