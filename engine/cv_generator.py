"""
🎯 GÉNÉRATEUR CV HYBRIDE (V5) - ONE-PAGE GUARANTEE + PROJETS
Architecture modulaire avec pools séparés pour garantir la présence des projets académiques.
"""

import asyncio
import copy
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
    "pro_experiences": {"target": 4, "minimum": 2},
    "projects": {"target": 2, "minimum": 1},
    "skills": {"target": 12, "minimum": 6},
    "max_bullets_pro": 2,
    "max_bullets_project": 0,
    "project_max_desc_chars": 150,
}

SHRINK_CONFIGS = [
    {"attempt": 1, "call_llm": True, "font_delta": 0.0, "max_pro": 4, "max_proj": 2},
    {"attempt": 2, "call_llm": False, "font_delta": -0.3, "max_pro": 4, "max_proj": 2},
    {"attempt": 3, "call_llm": False, "font_delta": -0.5, "max_pro": 4, "max_proj": 2},
    {"attempt": 4, "call_llm": True, "font_delta": -0.5, "max_pro": 3, "max_proj": 1},
]

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

    def _get_profile_project_ids(self, profile_id: str, all_experiences: List[Dict]) -> set[str]:
        """Détecte les IDs de projets liés au profil (priorités + type projet)."""
        profile_def = self.master_profile.get("profiles", {}).get(profile_id, {})
        priority_ids = set(profile_def.get("priority_experiences", []))
        by_id = {exp.get("id"): exp for exp in all_experiences if exp.get("id")}
        return {
            exp_id
            for exp_id in priority_ids
            if exp_id in by_id and by_id[exp_id].get("type") == "academic_project"
        }

    def _is_project_experience(self, exp: Dict, profile_project_ids: set[str]) -> bool:
        """Détermine si une entrée doit être traitée comme projet académique."""
        exp_id = exp.get("id", "")
        tags = [str(t).lower() for t in exp.get("profiles_tags", [])]
        project_tag_markers = {"project", "projects", "projet", "projets", "academic_project"}
        return (
            exp.get("type") == "academic_project"
            or exp_id in profile_project_ids
            or any(t in project_tag_markers for t in tags)
        )

    def rank_experiences_for_profile(self, all_experiences: List[Dict], profile_id: str, job_keywords: List[str]) -> Dict:
        """Sépare les expériences en 2 pools distincts : Pro et Projets."""
        pro_scored = []
        project_scored = []
        job_kw_set = set(k.lower() for k in job_keywords)
        profile_project_ids = self._get_profile_project_ids(profile_id, all_experiences)

        for exp in all_experiences:
            is_project = self._is_project_experience(exp, profile_project_ids)
            tags = exp.get("profiles_tags", [])
            tags_lower = {str(t).lower() for t in tags}
            exp_keywords = set(k.lower() for k in exp.get("K", []))
            keyword_overlap = len(exp_keywords & job_kw_set)

            if profile_id in tags_lower and keyword_overlap > 0:
                score = 4
            elif profile_id in tags_lower:
                score = 3
            elif "all" in tags_lower and keyword_overlap > 0:
                score = 2
            elif "all" in tags_lower:
                score = 1
            else:
                score = 0

            entry = {"data": exp, "score": score, "keyword_overlap": keyword_overlap}
            if is_project:
                project_scored.append(entry)
            else:
                pro_scored.append(entry)

        pro_scored.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)
        project_scored.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)

        pro_selected = [
            e["data"] for e in pro_scored if e["score"] > 0
        ][: CONTENT_BUDGET["pro_experiences"]["target"]]
        proj_selected = [
            e["data"] for e in project_scored if e["score"] > 0
        ][: CONTENT_BUDGET["projects"]["target"]]

        pro_with_floor = self._apply_floor(
            pro_selected, pro_scored, CONTENT_BUDGET["pro_experiences"]["minimum"]
        )
        proj_with_floor = self._apply_floor(
            proj_selected, project_scored, CONTENT_BUDGET["projects"]["minimum"]
        )
        floor_activated = (
            len(pro_with_floor) > len(pro_selected) or len(proj_with_floor) > len(proj_selected)
        )

        return {
            "pro_experiences": pro_with_floor,
            "projects": proj_with_floor,
            "floor_activated": floor_activated,
        }

    def _apply_floor(self, result: List[Dict], all_scored: List[Dict], minimum: int) -> List[Dict]:
        """Complète avec exclus (score 0) s'il manque du contenu."""
        if len(result) >= minimum:
            return result
        excluded = [e for e in all_scored if e["score"] == 0]
        excluded.sort(key=lambda x: x["keyword_overlap"], reverse=True)
        needed = minimum - len(result)
        return result + [e["data"] for e in excluded[:needed]]

    def enforce_project_guarantee(self, ranked_content: Dict, all_experiences: List[Dict], profile_id: str = "") -> Dict:
        """Garantit qu'au moins un projet est présent."""
        if len(ranked_content["projects"]) > 0:
            return ranked_content

        profile_project_ids = self._get_profile_project_ids(profile_id, all_experiences)
        fallback_projects = []
        for exp in all_experiences:
            if self._is_project_experience(exp, profile_project_ids):
                fallback_projects.append(exp)

        if fallback_projects:
            # Trier par semestre (S9 > S8...)
            def _parse_period(p):
                match = re.search(r'\d+', p)
                return int(match.group()) if match else 0
            
            fallback_projects.sort(key=lambda x: _parse_period(x.get("period", "")), reverse=True)
            ranked_content["projects"] = fallback_projects[:CONTENT_BUDGET["projects"]["target"]]
            print(f"      ⚠️ Fallback Projet(s) utilisé(s) : {len(ranked_content['projects'])}")

        return ranked_content

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        return await self.generate_one_page_cv(job)

    async def generate_one_page_cv(self, job: Dict) -> Dict:
        """Génère un CV avec Shrink Loop et séparation des pools Pro/Projets."""
        job_data = self._normalize_job(job)
        job_keywords = job_data.get("description", "").lower().split() # Simplifié pour le matching

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(job_data, self.master_profile)
        print(f"      → Profil cible : {profile_id.upper()} (Score: {match_score})")

        # 2. Classement et Pools
        all_exps = self.master_profile.get("experience_stark") or self.master_profile.get("experiences", [])
        ranked_content = self.rank_experiences_for_profile(all_exps, profile_id, job_keywords)
        ranked_content = self.enforce_project_guarantee(ranked_content, all_exps, profile_id)

        best_result = None
        cached_cv_data = None
        llm_calls = 0
        slug = self._slugify(f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}")
        output_base = DEFAULT_OUTPUT_DIR / f"cv_{slug}_{datetime.now().strftime('%Y%m%d_%H%M')}"

        for config in SHRINK_CONFIGS:
            attempt = config["attempt"]
            print(f"      → Tentative {attempt} ({config['max_pro']} Pro, {config['max_proj']} Proj, Font: {config['font_delta']})")
            
            current_pro = ranked_content["pro_experiences"][:config["max_pro"]]
            current_proj = ranked_content["projects"][:config["max_proj"]]
            
            filtered_skills = matching.filter_skills_by_profile(
                profile_id, self.master_profile, selected_experiences=current_pro + current_proj
            )
            candidate_context = prompts.build_candidate_context(profile_id, self.master_profile, current_pro, filtered_skills)
            candidate_context["ranked_projects"] = current_proj # Injecter les projets dans le contexte
            prompt_content_cfg = {
                "max_pro_exp": config["max_pro"],
                "min_pro_exp": CONTENT_BUDGET["pro_experiences"]["minimum"],
                "max_projects": config["max_proj"],
                "min_projects": CONTENT_BUDGET["projects"]["minimum"],
                "skills_count": CONTENT_BUDGET["skills"]["target"],
                "skills_min": CONTENT_BUDGET["skills"]["minimum"],
            }

            cv_data = {}
            if self.llm and config["call_llm"]:
                llm_calls += 1
                prompt_dict = prompts.build_generation_prompt(
                    job_data, candidate_context, profile_id, content_config=prompt_content_cfg
                )
                response_str = await self.llm.generate(json.dumps(prompt_dict, ensure_ascii=False))
                try:
                    clean_json = re.sub(r"```json\s*|\s*```", "", response_str).strip()
                    llm_output = json.loads(clean_json)
                    validation = prompts.post_process_llm_output(llm_output)
                    cv_data = self._assemble_final_data(validation["cv_data"], candidate_context)
                except Exception as e:
                    print(f"      ⚠️ Erreur LLM: {e}. Fallback.")
                    cv_data = self._assemble_fallback_data(candidate_context, job_data)
                cached_cv_data = copy.deepcopy(cv_data)
            elif cached_cv_data is not None:
                cv_data = copy.deepcopy(cached_cv_data)
            else:
                cv_data = self._assemble_fallback_data(candidate_context, job_data)
                cached_cv_data = copy.deepcopy(cv_data)

            fill_report = {
                "pro_count": len(current_pro),
                "project_count": len(current_proj),
                "skills_total": len(filtered_skills.get("hard_skills", [])),
                "floor_activated": ranked_content.get("floor_activated", False),
                "llm_calls": llm_calls,
                "shrink_attempt": attempt,
            }

            # Rendu PDF
            pdf_renderer = self.renderers["pdf"]
            pdf_path = pdf_renderer.render(cv_data, output_base, font_size_delta=config["font_delta"])
            
            if pdf_path:
                pages = pdf_renderer.get_page_count(pdf_path)
                print(f"      → Pages: {pages}")
                res = {"pdf_path": str(pdf_path), "page_count": pages, "cv_data": cv_data, "fill_report": fill_report}
                if pages == 1:
                    for f in ["md", "tex"]: 
                        p = self.renderers[f].render(cv_data, output_base)
                        if p: res[f"{f}_path"] = str(p)
                    return res
                best_result = res
            else:
                best_result = {"cv_data": cv_data, "fill_report": fill_report}
        
        return best_result or {"error": "Échec"}

    def _assemble_final_data(self, llm_output: Dict, context: Dict) -> Dict:
        cv_gen = llm_output.get("cv", {})
        
        # Expériences Pro (Pool A)
        final_exps = []
        gen_exps = {exp["id"]: exp for exp in cv_gen.get("experiences", [])}
        for exp in context["experiences"]:
            eid = exp.get("id")
            g = gen_exps.get(eid, {})
            fallback_achievements = exp.get("A", [])
            if isinstance(fallback_achievements, str):
                fallback_achievements = [fallback_achievements]
            final_exps.append({
                "position": g.get("rewritten_title", exp.get("title")),
                "company": exp.get("company"),
                "start_date": exp.get("period", "").split("-")[0].strip(),
                "end_date": exp.get("period", "").split("-")[-1].strip() if "-" in exp.get("period", "") else "",
                "location": exp.get("location", ""),
                "achievements": g.get("bullets", fallback_achievements)[:CONTENT_BUDGET["max_bullets_pro"]]
            })

        # Projets (Pool B)
        final_projs = []
        gen_projs = {p["id"]: p for p in cv_gen.get("projects", [])}
        for p in context.get("ranked_projects", []):
            pid = p.get("id")
            g = gen_projs.get(pid, {})
            final_projs.append({
                "name": g.get("rewritten_title", p.get("title")),
                "description": g.get("one_line_description", p.get("D", "")),
                "keywords": g.get("keywords_inline", " · ".join(p.get("K", [])))
            })

        skills_inline = cv_gen.get("skills_inline", "")
        if skills_inline:
            skills_names = [s.strip() for s in skills_inline.split("·") if s.strip()]
        else:
            context_skills = context.get("skills", {}).get("hard_skills", [])
            skills_names = [s.get("name", "").strip() for s in context_skills if s.get("name")]

        return {
            "identity": context["personal_info"],
            "headline": cv_gen.get("headline", {}).get("value", context["target_profile"]["headline"]),
            "summary": cv_gen.get("summary", {}).get("value", context["target_profile"]["summary"]),
            "experiences": final_exps,
            "projects": final_projs,
            "grouped_skills": {"Compétences": [{"name": s} for s in skills_names]} if skills_names else {},
            "education": [{"degree": e.get("degree"), "school": e.get("institution"), "year": e.get("period"), "details": e.get("specialization", "")} for e in context["education"]][:2],
            "languages": [{"name": l["language"], "level": l["level"]} for l in context["personal_info"].get("languages", [])]
        }

    def _assemble_fallback_data(self, context: Dict, job: Dict) -> Dict:
        return self._assemble_final_data({"cv": {}}, context)

    def _normalize_job(self, job: Dict) -> Dict:
        return {"title": str(job.get("title", "Ingénieur")), "company": str(job.get("company", "Entreprise")), "description": str(job.get("description", "")), "url": job.get("url", "")}

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower().replace(" ", "_")) or "cv"
