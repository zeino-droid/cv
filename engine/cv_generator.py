"""
🎯 GÉNÉRATEUR CV HYBRIDE (V5) - ONE-PAGE GUARANTEE + PROJETS
Architecture modulaire avec pools séparés pour garantir la présence des projets académiques.
"""

import asyncio
import copy
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Initialize logger
logger = logging.getLogger(__name__)

from engine import matching, prompts
from engine.cv_matcher import LocalExperienceMatcher

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
        "section_gap": 16,
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
        "leading": 0.55,
        "section_gap": 10,
        "margin_sides": 13,
    },
    {
        "attempt": 4,
        "call_llm": False,
        "max_pro_exp": 2,
        "max_projects": 1,
        "max_bullets": 2,
        "font_size": 9.2,
        "leading": 0.55,
        "section_gap": 6,
        "margin_sides": 12,
    },
    {
        "attempt": 5,
        "call_llm": False,
        "max_pro_exp": 2,
        "max_projects": 1,
        "max_bullets": 1,
        "font_size": 8.8,
        "leading": 0.52,
        "section_gap": 5,
        "margin_sides": 10,
    },
    {
        "attempt": 6,
        "call_llm": False,
        "max_pro_exp": 1,
        "max_projects": 1,
        "max_bullets": 1,
        "font_size": 8.5,
        "leading": 0.50,
        "section_gap": 4,
        "margin_sides": 8,
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

        self._log_status()

    def _log_status(self):
        logger.info(f"🧠 CERVEAU V5 — PROJETS + ONE-PAGE")
        name = self.master_profile.get("personal_info", {}).get("name", "Inconnu")
        logger.info(f"👤 Profil: {name}")
        logger.info(f"🤖 LLM:    {self.llm_name}")
        logger.info(
            f"📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}"
        )

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
        Vérifie les clés critiques avant le rendu Typst via Pydantic.
        Retourne la liste des erreurs — vide = OK.
        """
        from pydantic import ValidationError
        from engine.schemas import CVData

        try:
            CVData.model_validate(cv_data)
            return []
        except ValidationError as e:
            errors = []
            for err in e.errors():
                loc = ".".join([str(x) for x in err["loc"]])
                errors.append(f"❌ Erreur de structure : {loc} - {err['msg']}")
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
        self, all_experiences: List[Dict], profile_id: str, job_keywords: List[str], job_description: str = ""
    ) -> Dict:
        """3 passes : score → tri → backfill jusqu'au budget cible.
        V5+ : Combine scoring heuristique (tags) + TF-IDF sémantique (LocalExperienceMatcher)
        """
        pro_scored = []
        project_scored = []
        job_kw_set = {str(k).lower() for k in job_keywords}
        profile_project_ids = self._get_profile_project_ids(profile_id, all_experiences)

        # Calcul des scores sémantiques TF-IDF
        matcher = LocalExperienceMatcher()
        tfidf_scores = matcher.score_experiences_dict(all_experiences, job_description)

        job_haystack = job_description.lower()

        for index, exp in enumerate(all_experiences):
            is_project = self._is_project_experience(exp, profile_project_ids)
            exp_keywords = {str(k).lower() for k in exp.get("K", [])}
            # Un keyword de l'expérience matche si on le trouve dans la description
            keyword_overlap = sum(1 for kw in exp_keywords if kw in job_haystack)
            heuristic_score = self.score_experience(exp, profile_id, exp_keywords)
            
            entry_id = exp.get("id", f"exp_{index}")
            exp_data = exp if exp.get("id") else {**exp, "id": entry_id}
            
            # Combinaison : Heuristique dominante (10-100) + TF-IDF normalisé (0-10, pour départager)
            tfidf = tfidf_scores.get(entry_id, 0.0)
            combined_score = heuristic_score + (tfidf * 10.0)

            entry = {
                "id": entry_id,
                "data": exp_data,
                "score": combined_score,
                "keyword_overlap": keyword_overlap,
                "tfidf_score": tfidf,
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
            logger.warning(
                f"      ⚠️ Fallback Projet(s) utilisé(s) : {len(ranked_content['projects'])}"
            )

        return ranked_content

    async def generate_cv_for_job(
        self,
        job: Dict,
        headline_override: Optional[str] = None,
        summary_override: Optional[str] = None,
        section_overrides: Optional[Dict[str, Any]] = None,
        photo_path: Optional[str] = None,
    ) -> Dict:
        return await self.generate_one_page_cv(
            job,
            headline_override=headline_override,
            summary_override=summary_override,
            section_overrides=section_overrides,
            photo_path=photo_path,
        )

    async def generate_one_page_cv(
        self,
        job: Dict,
        headline_override: Optional[str] = None,
        summary_override: Optional[str] = None,
        section_overrides: Optional[Dict[str, Any]] = None,
        photo_path: Optional[str] = None,
    ) -> Dict:
        """Génère un CV avec Shrink Loop et séparation des pools Pro/Projets."""
        job_data = self._normalize_job(job)

        job_keywords = _extract_keywords(job_data.get("description", ""))

        # 1. Sélection du meilleur profil
        profile_id, match_score = matching.select_best_profile(
            job_data, self.master_profile
        )
        logger.info(f"Profil cible sélectionné : {profile_id.upper()} (Score: {match_score})")

        # 2. Classement et Pools
        all_exps = self.master_profile.get(
            "experience_stark"
        ) or self.master_profile.get("experiences", [])
        ranked_content = self.rank_experiences_for_profile(
            all_exps, profile_id, job_keywords, job_data.get("description", "")
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
            logger.info(
                f"Tentative {attempt} "
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
            # Action 3 : Injecter les mots-clés matchés (intersection profil × offre)
            profile_target_kw = {
                k.lower() for k in
                self.master_profile.get("profiles", {}).get(profile_id, {}).get("target_keywords", [])
            }
            job_haystack = f"{job_data.get('title', '')} {job_data.get('description', '')}".lower()
            candidate_context["matched_job_keywords"] = sorted([
                kw for kw in profile_target_kw if kw in job_haystack
            ])
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
                    logger.warning(f"Erreur LLM: {e}. Fallback aux données par défaut.", exc_info=True)
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

            # Hard-truncation logic for extreme shrink attempts
            if config["attempt"] >= 5 and "cv" in cv_data:
                # Fallback returns {"cv": {...}}, whereas LLM response assembled could be flat depending on data
                pass
            
            # Since the structure is flat (cv_data['summary'] directly) after assemble
            if config["attempt"] >= 5:
                # Truncate summary
                summary = cv_data.get("summary", "")
                if isinstance(summary, str) and len(summary) > 250:
                    cv_data["summary"] = prompts._truncate_at_sentence(summary, 240)
                
                # Truncate bullets
                for exp in cv_data.get("experiences", []):
                    exp["achievements"] = [
                        prompts._truncate_at_sentence(ach, 110) if isinstance(ach, str) and len(ach) > 110 else ach
                        for ach in exp.get("achievements", [])
                    ]
                
                # Remove education modules to save vertical space
                for edu in cv_data.get("education", []):
                    if "modules" in edu:
                        edu["modules"] = {}

            cv_data = self._apply_text_overrides(
                cv_data,
                headline_override=headline_override,
                summary_override=summary_override,
                section_overrides=section_overrides,
            )

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
                logger.warning(f"CV invalide (tentative {attempt}) :")
                for err in validation_errors:
                    logger.warning(f"  - {err}")
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
                photo_path=photo_path,
            )

            if pdf_path:
                pages = pdf_renderer.get_page_count(pdf_path)
                logger.info(f"Rendu Typst terminé. Pages détectées : {pages}")
                res = {
                    "pdf_path": str(pdf_path),
                    "page_count": pages,
                    "cv_data": cv_data,
                    "fill_report": fill_report,
                }
                if pages == 1:
                    self._render_additional_formats(cv_data, output_base, res)
                    return res
                best_result = res
            else:
                fallback_result = {"cv_data": cv_data, "fill_report": fill_report}
                self._render_additional_formats(cv_data, output_base, fallback_result)
                best_result = fallback_result

        return best_result or {"error": "Échec"}

    def _render_additional_formats(
        self, cv_data: Dict, output_base: Path, result: Dict
    ) -> None:
        """
        Rend les formats alternatifs Markdown/LaTeX pour un même contenu CV.

        Args:
            cv_data: Données CV à rendre.
            output_base: Chemin de base utilisé par les renderers.
            result: Dictionnaire résultat muté en place avec `md_path`/`tex_path` si rendus.

        Notes:
            Si un renderer est absent ou échoue (retourne None), le format concerné est ignoré.
        """
        for fmt in ["md", "tex"]:
            renderer = self.renderers.get(fmt)
            if renderer is None:
                continue
            rendered_path = renderer.render(cv_data, output_base)
            if rendered_path:
                result[f"{fmt}_path"] = str(rendered_path)

    def _apply_text_overrides(
        self,
        cv_data: Dict,
        headline_override: Optional[str] = None,
        summary_override: Optional[str] = None,
        section_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """
        Applique les overrides utilisateur sur le CV assemblé.

        - `headline_override` / `summary_override` : compatibilité historique.
        - `section_overrides` : overrides granulaires par section, schéma :
            {
              "headline": str,
              "summary": str,
              "achievements": {exp_id: [puce, ...]},
              "project_description": {proj_id: str},
              "project_keywords": {proj_id: str},
              "skills_hard": [str, ...],
              "skills_domain": [str, ...],
              "skills_soft": [str, ...],
            }
        Les overrides granulaires écrasent les overrides legacy si présents.
        """
        data = copy.deepcopy(cv_data)
        section_overrides = section_overrides or {}

        # 1. Headline & summary (overrides legacy + section_overrides)
        headline = (section_overrides.get("headline") or headline_override or "").strip()
        summary = (section_overrides.get("summary") or summary_override or "").strip()
        if headline:
            data["headline"] = re.sub(r"\s*:\s*", " : ", headline)
        if summary:
            data["summary"] = re.sub(r"\s*:\s*", " : ", summary)

        # 2. Achievements par expérience (clé = exp_id provenant du profil maître)
        ach_overrides = section_overrides.get("achievements") or {}
        if ach_overrides:
            for exp in data.get("experiences", []):
                eid = exp.get("id")
                # Fallback: matcher par titre/position si id ne matche pas
                match_key = eid if (eid and eid in ach_overrides) else exp.get("position")
                if match_key and match_key in ach_overrides:
                    new_bullets = [
                        re.sub(r"\s*:\s*", " : ", str(b)).strip()
                        for b in ach_overrides[match_key]
                        if str(b).strip()
                    ]
                    if new_bullets:
                        exp["achievements"] = new_bullets

        # 3. Description / mots-clés de projets (clé = proj_id)
        desc_overrides = section_overrides.get("project_description") or {}
        kw_overrides = section_overrides.get("project_keywords") or {}
        if desc_overrides or kw_overrides:
            for proj in data.get("projects", []):
                pid = proj.get("id")
                # Fallback: matcher par nom
                match_key = pid if (pid and (pid in desc_overrides or pid in kw_overrides)) else proj.get("name")
                if match_key and match_key in desc_overrides:
                    proj["description"] = str(desc_overrides[match_key]).strip()
                if match_key and match_key in kw_overrides:
                    proj["keywords"] = str(kw_overrides[match_key]).strip()

        # 4. Compétences (3 sous-groupes) — remplace TOUT le sous-groupe si présent
        grouped = data.setdefault("grouped_skills", {})
        skill_map = {
            "skills_hard": "Compétences Techniques",
            "skills_domain": "Connaissances Métier",
            "skills_soft": "Savoir-être",
        }
        for ov_key, group_label in skill_map.items():
            items = section_overrides.get(ov_key)
            if items is None:
                continue
            cleaned = [str(s).strip() for s in items if str(s).strip()]
            if cleaned:
                grouped[group_label] = [{"name": s} for s in cleaned]
            elif group_label in grouped:
                # liste vide explicite → on retire le groupe
                del grouped[group_label]

        return data

    def _assemble_final_data(
        self, llm_output: Dict, context: Dict, max_bullets: Optional[int] = None
    ) -> Dict:
        effective_max_bullets = (
            max_bullets if max_bullets is not None else FILL_BUDGET["max_bullets_pro"]
        )
        cv_gen = llm_output.get("cv", {})

        # Expériences Pro (Pool A)
        final_exps = []
        gen_exps = {exp["id"]: exp for exp in cv_gen.get("experiences", []) if exp.get("id")}
        for exp in context["experiences"]:
            eid = exp.get("id")
            if not eid:
                base = f"{exp.get('company', '')}_{exp.get('title', '')}".strip()
                eid = re.sub(r"[^a-z0-9_]", "", base.lower().replace(" ", "_")) or f"exp_{len(final_exps)}"
            
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
                    "id": eid,
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
        gen_projs = {p["id"]: p for p in cv_gen.get("projects", []) if p.get("id")}
        for p in context.get("ranked_projects", []):
            pid = p.get("id")
            if not pid:
                base = f"proj_{p.get('title', '')}".strip()
                pid = re.sub(r"[^a-z0-9_]", "", base.lower().replace(" ", "_")) or f"proj_{len(final_projs)}"
                
            g = gen_projs.get(pid, {})
            raw_proj_title = g.get("rewritten_title", p.get("title"))
            # Correction typographique française : espace avant les deux points
            rewritten_proj_title = re.sub(r"\s*:\s*", " : ", raw_proj_title)
            
            final_projs.append(
                {
                    "id": pid,
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
        """Fallback intelligent : adapte headline et summary au poste visé.

        Quand le LLM est indisponible (quota, crash, JSON malformé), ce
        fallback garantit que le CV reste ciblé sur l'offre plutôt que
        d'afficher les données brutes du profil.
        """
        job_title = job.get("title", "Ingénieur")
        company = job.get("company", "")
        candidate_name = context.get("personal_info", {}).get("name", "le candidat")
        profile_headline = context.get("target_profile", {}).get("headline", "")

        # --- Headline ciblé ---
        # On injecte le titre du poste dans le headline du profil
        targeted_headline = f"{profile_headline} | Candidature : {job_title}"
        if len(targeted_headline) > 100:
            targeted_headline = profile_headline  # fallback au headline profil (désormais propre)

        # --- Summary ciblé ---
        base_summary = context.get("target_profile", {}).get("summary", "")
        if company:
            targeted_summary = (
                f"{base_summary} "
                f"Candidature ciblée pour le poste de {job_title} chez {company}."
            )
        else:
            targeted_summary = base_summary

        # On injecte ces overrides dans un faux output LLM
        fake_llm = {
            "cv": {
                "headline": {"value": targeted_headline},
                "summary": {"value": targeted_summary},
            }
        }
        return self._assemble_final_data(fake_llm, context, max_bullets=max_bullets)

    def _normalize_job(self, job: Dict) -> Dict:
        return {
            "title": str(job.get("title", "Ingénieur")),
            "company": str(job.get("company", "Entreprise")),
            "description": str(job.get("description", "")),
            "url": job.get("url", ""),
        }

    def _slugify(self, value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower().replace(" ", "_")) or "cv"
