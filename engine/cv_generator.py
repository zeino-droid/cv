"""
🎯 GÉNÉRATEUR CV HYBRIDE (V5) - ONE-PAGE GUARANTEE + PROJETS
Architecture modulaire avec pools séparés pour garantir la présence des projets académiques.
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

# ============================================
# CONSTANTES DU BUDGET CONTENU (Phase 4)
# ============================================
CONTENT_BUDGET = {
    "max_pro_experiences": 2,     # Réduit de 3 à 2 pour laisser place aux projets
    "max_projects": 2,            # Slot garanti pour les projets
    "max_bullets_pro": 2,         # 2 bullets max par expérience pro
    "max_bullets_project": 0,     # Projets : format compact (pas de bullets)
    "project_max_desc_chars": 150 # Description courte
}

class PersonalCVGenerator:
    """Orchestrateur central du Cerveau avec garantie One-Page et Projets."""

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
        print(f"   🧠 CERVEAU V5 — PROJETS + ONE-PAGE")
        print(f"   {'=' * 40}")
        name = self.master_profile.get('personal_info', {}).get('name', 'Inconnu')
        print(f"   👤 Profil: {name}")
        print(f"   🤖 LLM:    {self.llm_name}")
        print(f"   📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}")
        print(f"   {'=' * 40}")

    def rank_experiences_for_profile(self, all_experiences: List[Dict], profile_id: str, job_keywords: List[str]) -> Dict:
        """Sépare les expériences en 2 pools distincts : Pro et Projets."""
        pro_pool = []
        project_pool = []
        job_kw_set = set(k.lower() for k in job_keywords)

        for exp in all_experiences:
            is_project = (exp.get("type") == "academic_project")
            tags = exp.get("profiles_tags", [])
            exp_keywords = set(k.lower() for k in exp.get("K", []))
            keyword_overlap = len(exp_keywords & job_kw_set)

            if profile_id in tags and keyword_overlap > 0:
                score = 3
            elif profile_id in tags:
                score = 2
            elif "all" in tags and keyword_overlap > 0:
                score = 1
            else:
                score = 0

            if score == 0: continue

            entry = {"data": exp, "score": score, "keyword_overlap": keyword_overlap}
            if is_project:
                project_pool.append(entry)
            else:
                pro_pool.append(entry)

        pro_pool.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)
        project_pool.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)

        return {
            "pro_experiences": [e["data"] for e in pro_pool[:CONTENT_BUDGET["max_pro_experiences"]]],
            "projects": [e["data"] for e in project_pool[:CONTENT_BUDGET["max_projects"]]]
        }

    def enforce_project_guarantee(self, ranked_content: Dict, all_experiences: List[Dict]) -> Dict:
        """Garantit qu'au moins un projet est présent."""
        if len(ranked_content["projects"]) > 0:
            return ranked_content

        fallback_projects = []
        for exp in all_experiences:
            if exp.get("type") == "academic_project":
                fallback_projects.append(exp)

        if fallback_projects:
            # Trier par semestre (S9 > S8...)
            def _parse_period(p):
                match = re.search(r'\d+', p)
                return int(match.group()) if match else 0
            
            fallback_projects.sort(key=lambda x: _parse_period(x.get("period", "")), reverse=True)
            ranked_content["projects"] = [fallback_projects[0]]
            print(f"      ⚠️ Fallback Projet utilisé : {fallback_projects[0].get('title')}")

        return ranked_content

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        """Génère un CV avec Shrink Loop et séparation des pools Pro/Projets."""
        job_data = self._normalize_job(job)
        job_keywords = job_data.get("description", "").lower().split() # Simplifié pour le matching

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(job_data, self.master_profile)
        print(f"      → Profil cible : {profile_id.upper()} (Score: {match_score})")

        # 2. Classement et Pools
        all_exps = self.master_profile.get("experiences", [])
        ranked_content = self.rank_experiences_for_profile(all_exps, profile_id, job_keywords)
        ranked_content = self.enforce_project_guarantee(ranked_content, all_exps)

        # 3. SHRINK LOOP (Phase 4)
        shrink_configs = [
            {"max_pro": 2, "max_proj": 2, "font_delta": 0.0},
            {"max_pro": 2, "max_proj": 1, "font_delta": -0.3},
            {"max_pro": 2, "max_proj": 1, "font_delta": -0.5},
        ]

        best_result = None
        slug = self._slugify(f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}")
        output_base = DEFAULT_OUTPUT_DIR / f"cv_{slug}_{datetime.now().strftime('%Y%m%d_%H%M')}"

        for attempt, config in enumerate(shrink_configs, 1):
            print(f"      → Tentative {attempt} ({config['max_pro']} Pro, {config['max_proj']} Proj, Font: {config['font_delta']})")
            
            current_pro = ranked_content["pro_experiences"][:config["max_pro"]]
            current_proj = ranked_content["projects"][:config["max_proj"]]
            
            filtered_skills = matching.filter_skills_by_profile(profile_id, self.master_profile)
            candidate_context = prompts.build_candidate_context(profile_id, self.master_profile, current_pro, filtered_skills)
            candidate_context["ranked_projects"] = current_proj # Injecter les projets dans le contexte

            cv_data = {}
            if self.llm:
                prompt_dict = prompts.build_generation_prompt(job_data, candidate_context, profile_id)
                response_str = await self.llm.generate(json.dumps(prompt_dict, ensure_ascii=False))
                try:
                    clean_json = re.sub(r"```json\s*|\s*```", "", response_str).strip()
                    llm_output = json.loads(clean_json)
                    validation = prompts.post_process_llm_output(llm_output)
                    cv_data = self._assemble_final_data(validation["cv_data"], candidate_context)
                except Exception as e:
                    print(f"      ⚠️ Erreur LLM: {e}. Fallback.")
                    cv_data = self._assemble_fallback_data(candidate_context, job_data)
            else:
                cv_data = self._assemble_fallback_data(candidate_context, job_data)

            # Rendu PDF
            pdf_renderer = self.renderers["pdf"]
            pdf_path = pdf_renderer.render(cv_data, output_base, font_size_delta=config["font_delta"])
            
            if pdf_path:
                pages = pdf_renderer.get_page_count(pdf_path)
                print(f"      → Pages: {pages}")
                res = {"pdf_path": str(pdf_path), "page_count": pages, "cv_data": cv_data}
                if pages == 1:
                    for f in ["md", "tex"]: 
                        p = self.renderers[f].render(cv_data, output_base)
                        if p: res[f"{f}_path"] = str(p)
                    return res
                best_result = res
        
        return best_result or {"error": "Échec"}

    def _assemble_final_data(self, llm_output: Dict, context: Dict) -> Dict:
        cv_gen = llm_output.get("cv", {})
        
        # Expériences Pro (Pool A)
        final_exps = []
        gen_exps = {exp["id"]: exp for exp in cv_gen.get("experiences", [])}
        for exp in context["experiences"]:
            eid = exp.get("id")
            if eid in gen_exps:
                g = gen_exps[eid]
                final_exps.append({
                    "position": g.get("rewritten_title", exp.get("title")),
                    "company": exp.get("company"),
                    "start_date": exp.get("period", "").split("-")[0].strip(),
                    "end_date": exp.get("period", "").split("-")[-1].strip() if "-" in exp.get("period", "") else "",
                    "location": exp.get("location", ""),
                    "achievements": g.get("bullets", exp.get("A", []))[:CONTENT_BUDGET["max_bullets_pro"]]
                })

        # Projets (Pool B)
        final_projs = []
        gen_projs = {p["id"]: p for p in cv_gen.get("projects", [])}
        for p in context.get("ranked_projects", []):
            pid = p.get("id")
            if pid in gen_projs:
                g = gen_projs[pid]
                final_projs.append({
                    "name": g.get("rewritten_title", p.get("title")),
                    "description": g.get("one_line_description", p.get("D", "")),
                    "keywords": g.get("keywords_inline", " · ".join(p.get("K", [])))
                })

        return {
            "identity": context["personal_info"],
            "headline": cv_gen.get("headline", {}).get("value", context["target_profile"]["headline"]),
            "summary": cv_gen.get("summary", {}).get("value", context["target_profile"]["summary"]),
            "experiences": final_exps,
            "projects": final_projs,
            "grouped_skills": {"Compétences": [{"name": s.strip()} for s in cv_gen.get("skills_inline", "").split("·")]} if cv_gen.get("skills_inline") else {},
            "education": [{"degree": e.get("degree"), "school": e.get("institution"), "year": e.get("period"), "details": e.get("specialization", "")} for e in context["education"]][:2],
            "languages": [{"name": l["language"], "level": l["level"]} for l in context["personal_info"].get("languages", [])]
        }

    def _assemble_fallback_data(self, context: Dict, job: Dict) -> Dict:
        return self._assemble_final_data({"cv": {}}, context)

    def _normalize_job(self, job: Dict) -> Dict:
        return {"title": str(job.get("title", "Ingénieur")), "company": str(job.get("company", "Entreprise")), "description": str(job.get("description", "")), "url": job.get("url", "")}

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower().replace(" ", "_")) or "cv"
