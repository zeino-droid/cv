"""
🎯 GÉNÉRATEUR CV HYBRIDE (V3)
Architecture modulaire: Matching + LLM (MLX/Ollama) + Rendering (Typst)
"""

import asyncio
import copy
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Imports locaux
from engine.engines import MLXEngine, OllamaEngine
from engine.matching import ProfileMatcher
from engine.prompts import CVPromptBuilder
from engine.rendering import LatexRenderer, MarkdownRenderer, TypstRenderer

DEFAULT_OUTPUT_DIR = Path("vault/resumes")


class PersonalCVGenerator:
    """Orchestrateur central du Cerveau"""

    def __init__(self, master_profile_path: str = "profiles/master_profile.json"):
        self.master_profile_path = Path(master_profile_path)

        # Charge master profile
        if not self.master_profile_path.exists():
            raise FileNotFoundError(
                f"Profil maître non trouvé à {self.master_profile_path}"
            )

        with open(self.master_profile_path, "r", encoding="utf-8") as f:
            self.master_profile = json.load(f)

        # Charger le profil complet (Markdown) pour le contexte étendu
        self.full_profile_md = ""
        full_profile_path = Path("profiles/full_profile.md")
        if full_profile_path.exists():
            with open(full_profile_path, "r", encoding="utf-8") as f:
                self.full_profile_md = f.read()

        # Initialise les composants
        self.matcher = ProfileMatcher(self.master_profile)
        self.prompt_builder = CVPromptBuilder(self.master_profile, self.full_profile_md)

        # Renderers
        self.renderers = {
            "pdf": TypstRenderer(),
            "md": MarkdownRenderer(),
            "tex": LatexRenderer(),
        }

        # LLM Engine selection
        self.mlx = MLXEngine()
        self.ollama = OllamaEngine()

        if self.mlx.available:
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
        print(f"   👤 Profil: {self.master_profile['identity']['name']}")
        print(f"   🤖 LLM:    {self.llm_name}")
        print(
            f"   📄 Typst:  {'✅ Actif' if self.renderers['pdf'].available else '❌ Manquant'}"
        )
        print(f"   {'=' * 40}")

    async def generate_cv_for_job(self, job: Dict) -> Dict:
        """Génère un CV complet pour une offre spécifique en un seul appel LLM (Fast Pipeline)."""
        job_data = self._normalize_job(job)
        print(f"\n   📄 GEN RAPIDE: {job_data.get('title')} @ {job_data.get('company')}")

        # 1. Sélection du CV de base (Simulation vs Énergie)
        desc_lower = job_data.get("description", "").lower() + " " + job_data.get("title", "").lower()
        simulation_keywords = ["simulation", "abaqus", "metafor", "fem", "calcul", "structure", "flambage", "buckling", "mécanique", "solidification", "matériaux"]
        energy_keywords = ["énergie", "energy", "thermique", "thermodynamique", "fluides", "fluent", "cfd", "procédés", "décarbonation", "pv", "solaire", "audit"]
        
        sim_score = sum(2 if k in job_data.get("title", "").lower() else 1 for k in simulation_keywords if k in desc_lower)
        en_score = sum(2 if k in job_data.get("title", "").lower() else 1 for k in energy_keywords if k in desc_lower)
        
        cv_type = "simulation" if sim_score >= en_score else "energy"
        print(f"      → Profil cible : {cv_type.upper()}")

        # 2. Matching compétences
        matched_skills = self.matcher.match_skills(job_data)
        achievements = self.matcher.select_achievements(job_data)
        
        headline = self.matcher.adapt_headline(job_data)
        summary = self.master_profile.get("summary", "").strip()

        # 3. Un seul appel LLM pour Headline + Summary Adaptation
        if self.llm:
            print(f"      → Adaptation IA (1 appel)...")
            from engine.prompts import CVPromptBuilder
            # Note: prompt_builder needs to implement build_fast_adaptation_prompt
            prompt = self.prompt_builder.build_fast_adaptation_prompt(job_data, matched_skills, cv_type)
            response = await self.llm.generate(prompt)
            improved = self._parse_json(response)
            
            if improved:
                headline = improved.get("headline", headline)
                summary = improved.get("summary", summary)
        # 4. Post-édition linguistique légère
        headline, summary, final_achievements = self._light_post_edit(
            headline=headline,
            summary=summary,
            achievements=[a["text"] for a in achievements[:5]],
            job=job_data,
        )

        # 5. Assemblage
        cv_data = self._assemble_data(
            job=job_data,
            headline=headline,
            summary=summary,
            skills=matched_skills[:10],
            achievements=final_achievements,
            cv_type=cv_type
        )

        # 5. Rendu
        slug = self._slugify(
            f"{job_data.get('company', 'job')}_{job_data.get('title', 'title')}"
        )
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

        print("   ✅ CV généré dans vault/resumes/")
        return {"cv_data": cv_data, **results}

    async def generate_batch(
        self, jobs: List[Dict], max_concurrency: int = 1
    ) -> List[Dict[str, Any]]:
        """Génère des CVs pour une liste d'offres avec parallélisme contrôlé."""
        if max_concurrency < 1:
            raise ValueError("max_concurrency doit être >= 1")

        print(f"\n   📋 BATCH: {len(jobs)} offres en cours...")
        semaphore = asyncio.Semaphore(max_concurrency)
        results: List[Dict[str, Any]] = []

        async def _run_single(job: Dict) -> Dict[str, Any]:
            async with semaphore:
                job_title = str(job.get("title", "Sans titre"))
                try:
                    generated = await self.generate_cv_for_job(job)
                    return {
                        "job_title": job_title,
                        "success": True,
                        "result": generated,
                    }
                except (ValueError, RuntimeError, OSError, KeyError, TypeError) as err:
                    print(f"   ❌ Erreur sur {job.get('company')}: {err}")
                    return {"job_title": job_title, "success": False, "error": str(err)}

        tasks = [_run_single(job) for job in jobs]
        for item in await asyncio.gather(*tasks):
            results.append(item)
        return results

    # --- Internals ---
    def _normalize_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        title = str(job.get("title", "")).strip() or "Poste non spécifié"
        company = str(job.get("company", "")).strip() or "Entreprise non spécifiée"
        description = str(job.get("description", "")).strip()
        required_skills_raw = job.get("required_skills", [])
        if isinstance(required_skills_raw, str):
            required_skills_raw = [required_skills_raw]
        elif not isinstance(required_skills_raw, list):
            required_skills_raw = []
        required_skills = [
            str(s).strip() for s in required_skills_raw if str(s).strip()
        ]
        return {
            **job,
            "title": title,
            "company": company,
            "description": description,
            "required_skills": required_skills,
        }

    def _coalesce_text(self, primary: Optional[str], fallback: str) -> str:
        if primary is None:
            return fallback
        cleaned = str(primary).strip().strip('"')
        return cleaned or fallback

    def _slugify(self, value: str) -> str:
        slug = value.lower().replace(" ", "_")
        slug = re.sub(r"[^a-z0-9_]", "", slug)
        return slug or "cv"

    def _light_post_edit(
        self,
        headline: str,
        summary: str,
        achievements: List[str],
        job: Dict,
    ) -> tuple[str, str, List[str]]:
        """
        Nettoyage linguistique léger et sûr :
        - supprime les espaces doubles
        - normalise les accents/ponctuations
        - enlève les fragments anglais les plus visibles
        - garde un ton naturel et lisible
        """
        forbidden = [
            "Passionné par",
            "Je suis motivé",
            "Suite à votre annonce",
            "I am",
            "team",
            "project",
            "Python scripting",
        ]

        def normalize(text: str) -> str:
            t = str(text or "").replace("\r", " ")
            t = unicodedata.normalize("NFKC", t)
            t = re.sub(r"\s+", " ", t).strip()
            for bad in forbidden:
                t = t.replace(bad, "")
            t = re.sub(r"\s+([,.;:!?])", r"\1", t)
            t = t.replace("  ", " ").strip()
            return t

        headline = normalize(headline)
        summary = normalize(summary)

        if headline.endswith("."):
            headline = headline[:-1].strip()
        if summary and summary[-1] not in ".!?":
            summary += "."

        cleaned_achievements: List[str] = []
        for ach in achievements:
            clean = normalize(ach).lstrip("•- ").strip()
            if clean:
                cleaned_achievements.append(f"• {clean}")

        english_markers = [
            "project",
            "team",
            "data",
            "model",
            "simulation",
            "analysis",
            "design",
            "tool",
            "workflow",
        ]
        english_hits = sum(1 for marker in english_markers if marker in summary.lower())
        if english_hits >= 5 and self.master_profile.get("summary"):
            summary = normalize(self.master_profile.get("summary", ""))

        return headline, summary, cleaned_achievements

    # --- Internals ---
    async def _get_semantic_skills(self, job: Dict) -> List[str]:
        res = await self.llm.generate(
            self.prompt_builder.build_semantic_expansion_prompt(job)
        )
        if not res:
            return []
        values = [s.strip() for s in res.split(",") if len(s.strip()) > 2]
        return list(dict.fromkeys(values))

    async def _generate_achievements(self, job: Dict, raw_ach: List[Dict]) -> List[str]:
        res = await self.llm.generate(
            self.prompt_builder.build_achievements_prompt(job, raw_ach)
        )
        if res:
            return [
                l.strip().lstrip("•- ").strip()
                for l in res.split("\n")
                if len(l.strip()) > 10
            ][:4]
        return [a["text"] for a in raw_ach[:4]]

    def _parse_json(self, text: str) -> Optional[Dict]:
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: extraire le premier objet JSON valide inclus dans un texte libre
        decoder = json.JSONDecoder()
        normalized = text.replace("\n", " ")
        for idx, char in enumerate(normalized):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(normalized[idx:])
                if isinstance(candidate, dict):
                    return candidate
            except json.JSONDecodeError:
                continue
        return None

    def _assemble_data(
        self,
        job: Dict,
        headline: str,
        summary: str,
        skills: List[str],
        achievements: List[str],
        cv_type: str = "simulation"
    ) -> Dict:
        """Fusionne le profil de base (Simulation ou Énergie) et les données générées."""
        base_profile_path = Path(f"profiles/{cv_type}.json")
        if base_profile_path.exists():
            with open(base_profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = copy.deepcopy(self.master_profile)

        data["headline"] = self._postprocess_title(headline)
        data["summary"] = self._postprocess_summary(summary)
        # Use simple target job info
        data["target_job"] = {"title": job.get("title"), "company": job.get("company")}

        # Inject key achievements into the latest experience
        if data.get("experiences"):
            data["experiences"][0]["achievements"] = [
                self._postprocess_bullet(a) for a in achievements
            ]

        # Strategic skill grouping
        data["grouped_skills"] = {
            "Expertise Technique": [{"name": s, "level": 4} for s in skills[:6]],
            "Outils & Digital": [
                {"name": s, "level": 3}
                for s in self.master_profile["skills"].get("tools", {}).keys()
            ][:5],
        }
        return data

    def _postprocess_title(self, text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        value = value.replace("  ", " ")
        value = value.strip('"').strip()
        if value and not value.endswith("."):
            return value
        return value.rstrip(".")

    def _postprocess_summary(self, text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        value = value.replace("  ", " ")
        value = value.strip('"').strip()
        value = re.sub(r"\s+([,.;:!?])", r"\1", value)
        if value and value[-1] not in ".!?":
            value += "."
        return value

    def _postprocess_bullet(self, text: str) -> str:
        value = re.sub(r"\s+", " ", str(text or "")).strip()
        value = value.lstrip("•- ").strip()
        value = re.sub(r"\s+([,.;:!?])", r"\1", value)
        if value and value[-1] not in ".!?":
            value += "."
        return f"• {value}"


async def main():
    """Point d'entrée CLI pour génération manuelle d'une offre."""
    gen = PersonalCVGenerator()
    print("\n   📝 Saisie manuelle de l'offre")
    title = input("   Poste ciblé: ").strip() or "Ingénieur R&D"
    company = input("   Entreprise: ").strip() or "Entreprise non spécifiée"
    description = input("   Description courte (optionnel): ").strip()
    raw_skills = input("   Compétences clés (séparées par virgules): ").strip()
    skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    job = {
        "title": title,
        "company": company,
        "description": description,
        "required_skills": skills,
    }
    await gen.generate_cv_for_job(job)


if __name__ == "__main__":
    asyncio.run(main())
