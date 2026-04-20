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
FILL_BUDGET = {
    "pro_experiences": 4,
    "pro_minimum": 2,
    "projects": 2,
    "projects_minimum": 1,
    "skills": 12,
    "skills_minimum": 6,
    "max_bullets_pro": 2,
}

CONTENT_BUDGET = {
    "max_bullets_project": 0,
    "project_max_desc_chars": 150,
}
BASE_FONT_SIZE = 9.5

SHRINK_CONFIGS = [
    {
        "attempt": 1,
        "call_llm": True,
        "max_pro_exp": 4,
        "max_projects": 2,
        "max_bullets": 3,
        "font_size": 9.5,
        "leading": 0.55,
        "section_gap": 5,
        "margin_sides": 14,
    },
    {
        "attempt": 2,
        "call_llm": False,
        "max_pro_exp": 4,
        "max_projects": 2,
        "max_bullets": 3,
        "font_size": 9.2,
        "leading": 0.50,
        "section_gap": 4,
        "margin_sides": 13,
    },
    {
        "attempt": 3,
        "call_llm": False,
        "max_pro_exp": 4,
        "max_projects": 2,
        "max_bullets": 3,
        "font_size": 9.0,
        "leading": 0.47,
        "section_gap": 3,
        "margin_sides": 12,
    },
    {
        "attempt": 4,
        "call_llm": True,
        "max_pro_exp": 3,
        "max_projects": 2,
        "max_bullets": 2,
        "font_size": 9.0,
        "leading": 0.47,
        "section_gap": 3,
        "margin_sides": 12,
    },
]

SCORE_PROFILE_WITH_KW = 4
SCORE_PROFILE_ONLY = 3
SCORE_ALL_WITH_KW = 2
SCORE_ALL_ONLY = 1
SCORE_OUT_OF_SCOPE = 0

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

    def score_experience(self, exp: Dict, profile_id: str, job_keywords_lower: set[str]) -> int:
        """Score cumulatif — aucune expérience jetée, tri seulement."""
        tags = {str(t).lower() for t in exp.get("profiles_tags", [])}
        kw_overlap = len({str(k).lower() for k in exp.get("K", [])} & job_keywords_lower)
        has_profile = profile_id.lower() in tags
        has_all = "all" in tags
        has_kw = kw_overlap > 0
        if has_profile and has_kw:
            return SCORE_PROFILE_WITH_KW
        if has_profile:
            return SCORE_PROFILE_ONLY
        if has_all and has_kw:
            return SCORE_ALL_WITH_KW
        if has_all or has_kw:
            return SCORE_ALL_ONLY
        return SCORE_OUT_OF_SCOPE

    def rank_experiences_for_profile(self, all_experiences: List[Dict], profile_id: str, job_keywords: List[str]) -> Dict:
        """3 passes : score → tri → backfill jusqu'au budget cible."""
        pro_scored = []
        project_scored = []
        job_kw_set = {str(k).lower() for k in job_keywords}
        profile_project_ids = self._get_profile_project_ids(profile_id, all_experiences)

        for index, exp in enumerate(all_experiences):
            is_project = self._is_project_experience(exp, profile_project_ids)
            exp_keywords = {str(k).lower() for k in exp.get("K", [])}
            keyword_overlap = len(exp_keywords & job_kw_set)
            score = self.score_experience(exp, profile_id, job_kw_set)
            entry_id = exp.get("id", f"exp_{index}")
            exp_data = exp if exp.get("id") else {**exp, "id": entry_id}
            entry = {
                "id": entry_id,
                "data": exp_data,
                "score": score,
                "keyword_overlap": keyword_overlap,
            }
            if is_project:
                project_scored.append(entry)
            else:
                pro_scored.append(entry)

        pro_scored.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)
        project_scored.sort(key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True)

        pro_result = [e["data"] for e in pro_scored[: FILL_BUDGET["pro_experiences"]]]
        proj_result = [e["data"] for e in project_scored[: FILL_BUDGET["projects"]]]
        pro_result, pro_backfilled = self._backfill_pool(
            pro_result,
            pro_scored,
            FILL_BUDGET["pro_minimum"],
            FILL_BUDGET["pro_experiences"],
            pool_name="pro_experiences",
        )
        proj_result, proj_backfilled = self._backfill_pool(
            proj_result,
            project_scored,
            FILL_BUDGET["projects_minimum"],
            FILL_BUDGET["projects"],
            pool_name="projects",
        )
        floor_activated = pro_backfilled or proj_backfilled

        return {
            "pro_experiences": pro_result,
            "projects": proj_result,
            "floor_activated": floor_activated,
            "fill_report": {
                "pro_count": len(pro_result),
                "project_count": len(proj_result),
                "pro_backfilled": pro_backfilled,
                "proj_backfilled": proj_backfilled,
                "floor_activated": floor_activated,
                "pro_ids_selected": [e.get("id", "?") for e in pro_result],
                "project_ids_selected": [e.get("id", "?") for e in proj_result],
            },
        }

    def _backfill_pool(
        self,
        current: List[Dict],
        all_scored: List[Dict],
        minimum: int,
        target: int,
        pool_name: str = "pool",
    ) -> tuple[List[Dict], bool]:
        if minimum > target:
            raise ValueError(
                f"Configuration error in {pool_name}: minimum ({minimum}) "
                f"cannot exceed target ({target})"
            )
        if len(current) >= target:
            return current, False
        selected_ids = {e.get("id") for e in current if e.get("id")}
        remaining = sorted(
            [e for e in all_scored if e["id"] not in selected_ids],
            key=lambda x: (x["score"], x["keyword_overlap"]),
            reverse=True,
        )
        candidates = remaining[: target - len(current)]
        backfilled = len(candidates) > 0
        for candidate in candidates:
            current.append(candidate["data"])
        return current, backfilled

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
            ranked_content["projects"] = fallback_projects[: FILL_BUDGET["projects"]]
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
            print(
                f"      → Tentative {attempt} "
                f"({config['max_pro_exp']} Pro, {config['max_projects']} Proj, Font: {config['font_size']})"
            )
            
            current_pro = ranked_content["pro_experiences"][: config["max_pro_exp"]]
            current_proj = ranked_content["projects"][: config["max_projects"]]
            
            filtered_skills = matching.filter_skills_by_profile(
                profile_id, self.master_profile, selected_experiences=current_pro + current_proj
            )
            candidate_context = prompts.build_candidate_context(profile_id, self.master_profile, current_pro, filtered_skills)
            candidate_context["ranked_projects"] = current_proj # Injecter les projets dans le contexte
            prompt_content_cfg = {
                "max_pro_exp": config["max_pro_exp"],
                "min_pro_exp": FILL_BUDGET["pro_minimum"],
                "max_projects": config["max_projects"],
                "min_projects": FILL_BUDGET["projects_minimum"],
                "max_bullets": config["max_bullets"],
                "skills_count": FILL_BUDGET["skills"],
                "skills_min": FILL_BUDGET["skills_minimum"],
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
                    cv_data = self._assemble_final_data(
                        validation["cv_data"],
                        candidate_context,
                        max_bullets=config["max_bullets"],
                    )
                except Exception as e:
                    print(f"      ⚠️ Erreur LLM: {e}. Fallback.")
                    cv_data = self._assemble_fallback_data(
                        candidate_context,
                        job_data,
                        max_bullets=config["max_bullets"],
                    )
                cached_cv_data = copy.deepcopy(cv_data)
            elif cached_cv_data is not None:
                cv_data = copy.deepcopy(cached_cv_data)
            else:
                cv_data = self._assemble_fallback_data(
                    candidate_context,
                    job_data,
                    max_bullets=config["max_bullets"],
                )
                cached_cv_data = copy.deepcopy(cv_data)

            rank_fill_report = ranked_content.get("fill_report", {})
            skill_fill_layers = filtered_skills.get("fill_layers", {})
            fill_report = {
                "pro_count": len(current_pro),
                "project_count": len(current_proj),
                "skills_total": len(filtered_skills.get("hard_skills", [])),
                "floor_activated": ranked_content.get("floor_activated", False),
                "llm_calls": llm_calls,
                "shrink_attempt": attempt,
                "pro_backfilled": rank_fill_report.get("pro_backfilled", False),
                "proj_backfilled": rank_fill_report.get("proj_backfilled", False),
                "pro_ids_selected": rank_fill_report.get("pro_ids_selected", []),
                "project_ids_selected": rank_fill_report.get("project_ids_selected", []),
                "layer_1_signature": skill_fill_layers.get("layer_1_signature", 0),
                "layer_2_transversal": skill_fill_layers.get("layer_2_transversal", 0),
            }

            # Rendu PDF
            pdf_renderer = self.renderers["pdf"]
            font_delta = config["font_size"] - BASE_FONT_SIZE
            pdf_path = pdf_renderer.render(
                cv_data,
                output_base,
                font_size_delta=font_delta,
                leading=config["leading"],
                section_gap=config["section_gap"],
                margin_sides=config["margin_sides"],
            )
            
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

    def _assemble_final_data(self, llm_output: Dict, context: Dict, max_bullets: Optional[int] = None) -> Dict:
        effective_max_bullets = (
            max_bullets if max_bullets is not None else FILL_BUDGET["max_bullets_pro"]
        )
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
                "achievements": g.get("bullets", fallback_achievements)[:effective_max_bullets],
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

    def _assemble_fallback_data(
        self, context: Dict, job: Dict, max_bullets: Optional[int] = None
    ) -> Dict:
        return self._assemble_final_data({"cv": {}}, context, max_bullets=max_bullets)

    def _normalize_job(self, job: Dict) -> Dict:
        return {"title": str(job.get("title", "Ingénieur")), "company": str(job.get("company", "Entreprise")), "description": str(job.get("description", "")), "url": job.get("url", "")}

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower().replace(" ", "_")) or "cv"
