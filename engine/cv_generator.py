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
from typing import Any, Dict, List, Optional, Set, Tuple

from engine import matching, prompts

# Imports locaux
from engine.engines import GeminiEngine, MLXEngine, OllamaEngine
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

STOPWORDS_FR = {
    "le",
    "la",
    "les",
    "de",
    "du",
    "des",
    "un",
    "une",
    "et",
    "en",
    "au",
    "aux",
    "par",
    "sur",
    "dans",
    "pour",
    "avec",
    "qui",
    "que",
    "quoi",
    "dont",
    "où",
    "est",
    "son",
    "sa",
    "ses",
    "leur",
    "leurs",
    "ce",
    "cet",
    "cette",
    "ces",
    "plus",
    "mais",
    "ou",
    "donc",
    "or",
    "ni",
    "car",
    "très",
    "bien",
    "aussi",
    "tout",
    "tous",
    "toute",
    "toutes",
    "être",
    "avoir",
    "faire",
    "ils",
    "elles",
    "nous",
    "vous",
    "ils",
    "on",
    "se",
    "si",
    "ne",
    "pas",
    "une",
    "nos",
    "vos",
}


def _extract_keywords(text: str) -> List[str]:
    """Extrait les tokens significatifs d'un texte (sans stopwords, sans ponctuation)."""
    tokens = re.findall(r"\b[a-zA-ZÀ-ÿ]{3,}\b", text.lower())
    return [t for t in tokens if t not in STOPWORDS_FR]


SHRINK_CONFIGS = [
    {
        "attempt": 1,
        "call_llm": True,
        "max_pro_exp": 4,
        "max_projects": 2,
        "max_bullets": 2,
        "font_size": 10.4,
        "leading": 0.65,
        "section_gap": 22,
        "margin_sides": 18,
    },
    {
        "attempt": 2,
        "call_llm": False,
        "max_pro_exp": 3,
        "max_projects": 2,
        "max_bullets": 2,
        "font_size": 9.8,
        "leading": 0.58,
        "section_gap": 14,
        "margin_sides": 15,
    },
    {
        "attempt": 3,
        "call_llm": False,
        "max_pro_exp": 3,
        "max_projects": 1,
        "max_bullets": 1,
        "font_size": 9.2,
        "leading": 0.54,
        "section_gap": 10,
        "margin_sides": 13,
    },
    {
        "attempt": 4,
        "call_llm": False,
        "max_pro_exp": 2,
        "max_projects": 1,
        "max_bullets": 2,
        "font_size": 8.6,
        "leading": 0.48,
        "section_gap": 6,
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
            raise FileNotFoundError(
                f"Profil maître non trouvé à {self.master_profile_path}"
            )

        self.master_profile = matching.load_profile_index(str(self.master_profile_path))

        # Renderers
        self.renderers = {
            "pdf": TypstRenderer(),
            "md": MarkdownRenderer(),
            "tex": LatexRenderer(),
        }

        # LLM Engine selection
        import os

        gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
            "OPENAI_API_KEY"
        )

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
        name = self.master_profile.get("personal_info", {}).get("name", "Inconnu")
        print(f"   👤 Profil: {name}")
        print(f"   🤖 LLM:    {self.llm_name}")
        print(
            f"   📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}"
        )
        print(f"   {'=' * 40}")

    _CV_SCHEMA: Dict[str, Any] = {
        "identity": {"_required": True, "_fields": ["name", "email", "phone"]},
        "headline": {"_required": True, "_fields": []},
        "summary": {"_required": True, "_fields": []},
        "experiences": {"_required": True, "_fields": []},
        "education": {"_required": True, "_fields": []},
        "projects": {"_required": False, "_fields": []},
        "grouped_skills": {"_required": False, "_fields": []},
        "languages": {"_required": False, "_fields": []},
        "hobbies": {"_required": False, "_fields": []},
    }

    def _validate_cv_data(self, cv_data: Dict) -> List[str]:
        """
        Vérifie les clés critiques avant le rendu Typst.
        Retourne la liste des erreurs — vide = OK.
        """
        errors = []
        for section, rules in self._CV_SCHEMA.items():
            if rules["_required"] and section not in cv_data:
                errors.append(f"❌ Section obligatoire manquante : '{section}'")
                continue
            if section not in cv_data:
                continue
            for field in rules.get("_fields", []):
                if field not in (cv_data[section] or {}):
                    errors.append(f"⚠️  Champ manquant : '{section}.{field}'")
        return errors

    def _get_profile_project_ids(
        self, profile_id: str, all_experiences: List[Dict]
    ) -> Set[str]:
        """Détecte les IDs de projets liés au profil (priorités + type projet)."""
        profile_def = self.master_profile.get("profiles", {}).get(profile_id, {})
        priority_ids = set(profile_def.get("priority_experiences", []))
        by_id = {exp.get("id"): exp for exp in all_experiences if exp.get("id")}
        return {
            exp_id
            for exp_id in priority_ids
            if exp_id in by_id and by_id[exp_id].get("type") == "academic_project"
        }

    def _is_project_experience(self, exp: Dict, profile_project_ids: Set[str]) -> bool:
        """Détermine si une entrée doit être traitée comme projet académique."""
        exp_id = exp.get("id", "")
        tags = [str(t).lower() for t in exp.get("profiles_tags", [])]
        project_tag_markers = {
            "project",
            "projects",
            "projet",
            "projets",
            "academic_project",
        }
        return (
            exp.get("type") == "academic_project"
            or exp_id in profile_project_ids
            or any(t in project_tag_markers for t in tags)
        )

    def score_experience(
        self, exp: Dict, profile_id: str, job_keywords_lower: Set[str]
    ) -> int:
        """Score cumulatif — aucune expérience jetée, tri seulement."""
        tags = {str(t).lower() for t in exp.get("profiles_tags", [])}
        kw_overlap = len(
            {str(k).lower() for k in exp.get("K", [])} & job_keywords_lower
        )
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

    def rank_experiences_for_profile(
        self, all_experiences: List[Dict], profile_id: str, job_keywords: List[str]
    ) -> Dict:
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
        project_scored.sort(
            key=lambda x: (x["score"], x["keyword_overlap"]), reverse=True
        )

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
    ) -> Tuple[List[Dict], bool]:
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

    def enforce_project_guarantee(
        self, ranked_content: Dict, all_experiences: List[Dict], profile_id: str = ""
    ) -> Dict:
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
            def _parse_period(p: str) -> Tuple[int, int]:
                sem_match = re.search(
                    r"\bS(\d{1,2})\b|\bSemestre\s+(\d{1,2})\b", p, re.IGNORECASE
                )
                if sem_match:
                    val = int(sem_match.group(1) or sem_match.group(2))
                    return (1, val)

                year_match = re.search(r"\b(20\d{2})\b", p)
                if year_match:
                    return (0, int(year_match.group(1)))

                return (0, 0)

            fallback_projects.sort(
                key=lambda x: _parse_period(x.get("period", "")), reverse=True
            )
            ranked_content["projects"] = fallback_projects[: FILL_BUDGET["projects"]]
            print(
                f"      ⚠️ Fallback Projet(s) utilisé(s) : {len(ranked_content['projects'])}"
            )

        return ranked_content

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        return await self.generate_one_page_cv(job)

    async def generate_one_page_cv(self, job: Dict) -> Dict:
        """Génère un CV avec Shrink Loop et séparation des pools Pro/Projets."""
        job_data = self._normalize_job(job)

        job_keywords = _extract_keywords(job_data.get("description", ""))

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(
            job_data, self.master_profile
        )
        print(f"      → Profil cible : {profile_id.upper()} (Score: {match_score})")

        # 2. Classement et Pools
        all_exps = self.master_profile.get(
            "experience_stark"
        ) or self.master_profile.get("experiences", [])
        ranked_content = self.rank_experiences_for_profile(
            all_exps, profile_id, job_keywords
        )
        ranked_content = self.enforce_project_guarantee(
            ranked_content, all_exps, profile_id
        )

        best_result = None
        cached_cv_data = None
        llm_calls = 0
        cached_llm_result = None
        slug = self._slugify(
            f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}"
        )
        output_base = (
            DEFAULT_OUTPUT_DIR / f"cv_{slug}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )

        for config in SHRINK_CONFIGS:
            attempt = config["attempt"]
            print(
                f"      → Tentative {attempt} "
                f"({config['max_pro_exp']} Pro, {config['max_projects']} Proj, Font: {config['font_size']})"
            )

            current_pro = ranked_content["pro_experiences"][: config["max_pro_exp"]]
            current_proj = ranked_content["projects"][: config["max_projects"]]

            filtered_skills = matching.filter_skills_by_profile(
                profile_id,
                self.master_profile,
                selected_experiences=current_pro + current_proj,
            )
            candidate_context = prompts.build_candidate_context(
                profile_id, self.master_profile, current_pro, filtered_skills
            )
            candidate_context["ranked_projects"] = (
                current_proj  # Injecter les projets dans le contexte
            )
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
            should_call_llm = (
                self.llm is not None and config["call_llm"] and llm_calls == 0
            )
            if should_call_llm:
                llm_calls += 1
                prompt_dict = prompts.build_generation_prompt(
                    job_data,
                    candidate_context,
                    profile_id,
                    content_config=prompt_content_cfg,
                )
                response_str = await self.llm.generate(
                    json.dumps(prompt_dict, ensure_ascii=False)
                )
                try:
                    clean_json = re.sub(r"```json\s*|\s*```", "", response_str).strip()
                    llm_output = json.loads(clean_json)
                    validation = prompts.post_process_llm_output(
                        llm_output, content_config=prompt_content_cfg
                    )
                    cached_llm_result = validation["cv_data"]
                    cv_data = self._assemble_final_data(
                        cached_llm_result,
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
            elif cached_llm_result is not None:
                # Re-assemblage intelligent à partir de la sortie LLM déjà validée
                # mais avec les nouvelles contraintes de troncature (max_bullets)
                cv_data = self._assemble_final_data(
                    cached_llm_result,
                    candidate_context,
                    max_bullets=config["max_bullets"],
                )
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
                "project_ids_selected": rank_fill_report.get(
                    "project_ids_selected", []
                ),
                "layer_1_signature": skill_fill_layers.get("layer_1_signature", 0),
                "layer_2_transversal": skill_fill_layers.get("layer_2_transversal", 0),
            }

            validation_errors = self._validate_cv_data(cv_data)
            if validation_errors:
                print(f"      ⚠️  CV invalide (tentative {attempt}) :")
                for err in validation_errors:
                    print(f"         {err}")
                if any("❌" in e for e in validation_errors):
                    best_result = {
                        "cv_data": cv_data,
                        "fill_report": fill_report,
                        "validation_errors": validation_errors,
                    }
                    continue

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
                res = {
                    "pdf_path": str(pdf_path),
                    "page_count": pages,
                    "cv_data": cv_data,
                    "fill_report": fill_report,
                }
                if pages == 1:
                    for f in ["md", "tex"]:
                        p = self.renderers[f].render(cv_data, output_base)
                        if p:
                            res[f"{f}_path"] = str(p)
                    return res
                best_result = res
            else:
                best_result = {"cv_data": cv_data, "fill_report": fill_report}

        return best_result or {"error": "Échec"}

    def _assemble_final_data(
        self, llm_output: Dict, context: Dict, max_bullets: Optional[int] = None
    ) -> Dict:
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

            # Gestion intelligente du Fallback pour STAR-K (A est souvent un bloc de texte)
            fallback_achievements = exp.get("A", [])
            if isinstance(fallback_achievements, str):
                # Découper le bloc de texte en phrases si c'est un paragraphe unique
                sentences = [
                    s.strip()
                    for s in re.split(r"(?<=[.!?])\s+", fallback_achievements)
                    if len(s.strip()) > 10
                ]
                fallback_achievements = (
                    sentences if len(sentences) > 1 else [fallback_achievements]
                )

            raw_title = g.get("rewritten_title", exp.get("title"))
            # Correction typographique française : espace avant les deux points
            rewritten_title = re.sub(r"\s*:\s*", " : ", raw_title)
            
            # Cas spécial : Jumeau Numérique -> Jumeau Numérique : Sujet
            if "jumeau numérique" in rewritten_title.lower() and ":" not in rewritten_title:
                rewritten_title = re.sub(r"(?i)jumeau numérique\s+", "Jumeau Numérique : ", rewritten_title)

            final_exps.append(
                {
                    "position": rewritten_title,
                    "company": exp.get("company"),
                    "start_date": exp.get("period", "").split("-")[0].strip(),
                    "end_date": exp.get("period", "").split("-")[-1].strip()
                    if "-" in exp.get("period", "")
                    else "",
                    "location": exp.get("location", ""),
                    "achievements": [
                        re.sub(r"\s*:\s*", " : ", a)
                        for a in g.get("bullets", fallback_achievements)[
                            :effective_max_bullets
                        ]
                    ],
                }
            )

        # Regroupement par entreprise (fix fusion Typst)
        seen_companies = []
        grouped_exps = []
        # On garde l'ordre original mais on tire les expériences de la même boîte ensemble
        temp_exps = list(final_exps)
        while temp_exps:
            current = temp_exps.pop(0)
            grouped_exps.append(current)
            # Chercher les autres de la même boîte
            others = [x for x in temp_exps if x["company"] == current["company"]]
            for o in others:
                grouped_exps.append(o)
                temp_exps.remove(o)
        final_exps = grouped_exps

        # Projets (Pool B)
        final_projs = []
        gen_projs = {p["id"]: p for p in cv_gen.get("projects", [])}
        for p in context.get("ranked_projects", []):
            pid = p.get("id")
            g = gen_projs.get(pid, {})
            raw_proj_title = g.get("rewritten_title", p.get("title"))
            # Correction typographique française : espace avant les deux points
            rewritten_proj_title = re.sub(r"\s*:\s*", " : ", raw_proj_title)
            
            final_projs.append(
                {
                    "name": rewritten_proj_title,
                    "description": g.get("one_line_description", p.get("D", "")),
                    "keywords": g.get("keywords_inline", " · ".join(p.get("K", []))),
                }
            )

        skills_inline_raw = cv_gen.get("skills_inline", "")
        context_hard_skills = context.get("skills", {}).get("hard_skills", [])

        grouped_skills = {}

        if skills_inline_raw:
            llm_skills = [s.strip() for s in skills_inline_raw.split("·") if s.strip()]
            if llm_skills:
                grouped_skills["Compétences Techniques"] = [
                    {"name": s} for s in llm_skills[:12]
                ]
        else:
            if context_hard_skills:
                grouped_skills["Compétences Techniques"] = [
                    {"name": s.get("name", "").strip()}
                    for s in context_hard_skills
                    if s.get("name")
                ][:6]
            context_domain = context.get("skills", {}).get("domain_knowledge", [])
            if context_domain:
                grouped_skills["Connaissances Métier"] = [
                    {"name": d.strip()} for d in context_domain if d.strip()
                ][:6]
            
            context_soft = context.get("skills", {}).get("soft_skills", [])
            if context_soft:
                grouped_skills["Savoir-être"] = [
                    {"name": s.strip()} for s in context_soft if s.strip()
                ][:5]


        return {
            "identity": context["personal_info"],
            "headline": re.sub(
                r"\s*:\s*",
                " : ",
                cv_gen.get("headline", {}).get(
                    "value", context["target_profile"]["headline"]
                ),
            ),
            "summary": re.sub(
                r"\s*:\s*",
                " : ",
                cv_gen.get("summary", {}).get(
                    "value", context["target_profile"]["summary"]
                ),
            ),
            "experiences": final_exps,
            "projects": final_projs,
            "grouped_skills": grouped_skills,
            "education": [
                {
                    "degree": e.get("degree"),
                    "school": e.get("institution"),
                    "year": e.get("period"),
                    "specialization": e.get("specialization"),
                    "details": e.get("details", ""),
                    "modules": e.get("curriculum_highlights", {})
                    if "ENSEM" in (e.get("institution") or "")
                    else {},
                }
                for e in context["education"]
            ][:2],
            "languages": [
                {"name": l["language"], "level": l["level"]}
                for l in context["personal_info"].get("languages", [])
            ],
            "hobbies": context["personal_info"].get("hobbies", []),
        }

    def _assemble_fallback_data(
        self, context: Dict, job: Dict, max_bullets: Optional[int] = None
    ) -> Dict:
        return self._assemble_final_data({"cv": {}}, context, max_bullets=max_bullets)

    def _normalize_job(self, job: Dict) -> Dict:
        return {
            "title": str(job.get("title", "Ingénieur")),
            "company": str(job.get("company", "Entreprise")),
            "description": str(job.get("description", "")),
            "url": job.get("url", ""),
        }

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower().replace(" ", "_")) or "cv"
