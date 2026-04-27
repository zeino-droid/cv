"""
Orchestrateur principal du sourcing France-First.

Appelle les 3 sources en parallèle (ThreadPoolExecutor),
normalise → déduplique → score → re-rank IA → extrait skills → renvoie.
"""

from __future__ import annotations

import json as _json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Callable, Dict, List, Optional

import yaml

from engine.sourcing import adzuna, companies_watcher, france_travail
from engine.sourcing.ranking import (
    deduplicate_smart,
    expand_keywords_with_llm,
    has_gemini,
    llm_extract_skills,
    llm_rerank_top,
    score_job,
)

ROOT = Path(__file__).parent.parent.parent
SEARCH_CONFIG_PATH = ROOT / "profiles" / "search_config.yaml"
MASTER_PROFILE_PATH = ROOT / "profiles" / "master_profile.json"


# ──────────────────────────────────────────────────────────────────
#  Chargement config & profil
# ──────────────────────────────────────────────────────────────────

def load_config() -> Dict:
    if SEARCH_CONFIG_PATH.exists():
        with open(SEARCH_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_master_profile() -> Dict:
    if MASTER_PROFILE_PATH.exists():
        with open(MASTER_PROFILE_PATH, "r", encoding="utf-8") as f:
            return _json.load(f)
    return {}


# ──────────────────────────────────────────────────────────────────
#  Orchestrateur
# ──────────────────────────────────────────────────────────────────

class _ProgressBus:
    """Petit bus thread-safe pour répartir 0→1 entre 3 sources qui tournent en parallèle."""

    def __init__(self, callback: Optional[Callable[[float, str], None]], slots: List[float]):
        self._callback = callback
        self._slots = slots  # ex [0.05, 0.50, 0.30] = poids relatifs des sources
        self._progress = [0.0] * len(slots)
        self._lock = Lock()
        self._base = 0.05
        self._cap = 0.65  # on garde 0.65→1.0 pour la phase post-traitement

    def update(self, slot: int, fraction: float, message: str):
        if not self._callback:
            return
        fraction = max(0.0, min(1.0, fraction))
        with self._lock:
            self._progress[slot] = fraction
            total_weight = sum(self._slots) or 1.0
            weighted = sum(p * w for p, w in zip(self._progress, self._slots)) / total_weight
            pct = self._base + (self._cap - self._base) * weighted
            try:
                self._callback(pct, message)
            except Exception:
                pass


def scan_jobs(
    selected_categories: Optional[List[str]] = None,
    departments: Optional[List[str]] = None,
    extra_keywords: Optional[List[str]] = None,
    use_llm_expansion: bool = True,
    use_llm_rerank: bool = True,
    use_llm_skills: bool = True,
    enable_france_travail: bool = True,
    enable_adzuna: bool = True,
    enable_companies_watcher: bool = True,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict:
    """
    Pipeline complet. Renvoie un dict :
      {
        "jobs": [...],          # liste finale triée
        "by_source": {...},     # compteur par source
        "warnings": [...],      # messages user-facing (clés manquantes, etc.)
        "summary": "…",
      }

    `selected_categories` : pour le Companies Watcher (ex ["editeurs_simu", "energie"])
    `departments`         : codes département pour France Travail (ex ["75","69","31"])
    `extra_keywords`      : mots-clés ajoutés manuellement par l'utilisateur
    """
    def report(p: float, msg: str):
        if progress_callback:
            try:
                progress_callback(min(max(p, 0.0), 1.0), msg)
            except Exception:
                pass

    def stopped() -> bool:
        return bool(should_stop and should_stop())

    config = load_config()
    profile = load_master_profile()

    search_cfg = config.get("search", {}) or {}
    rome_codes: List[str] = list(search_cfg.get("rome_codes") or [])
    base_keywords: List[str] = list(search_cfg.get("keywords") or [])
    publiee_depuis: int = int(search_cfg.get("publiee_depuis", 31))
    max_per_query: int = int(search_cfg.get("max_per_query", 100))

    keywords = list(dict.fromkeys((extra_keywords or []) + base_keywords))

    # 1. Expansion sémantique des mots-clés (utilisée par Adzuna et Companies Watcher)
    if use_llm_expansion and has_gemini() and not stopped() and keywords:
        report(0.03, "🧠 Expansion sémantique des mots-clés (Gemini)…")
        keywords = expand_keywords_with_llm(keywords, profile, max_extra_per_keyword=2)

    if stopped():
        return {"jobs": [], "by_source": {}, "warnings": ["Annulé par l'utilisateur."],
                "summary": "Annulé."}

    warnings: List[str] = []

    # 2. Vérification des sources actives
    sources_active: List[str] = []
    if enable_france_travail:
        if france_travail.has_credentials():
            sources_active.append("france_travail")
        else:
            warnings.append(
                "🇫🇷 France Travail désactivé : ajoute FT_CLIENT_ID et FT_CLIENT_SECRET "
                "(inscription gratuite 5 min sur https://francetravail.io/)."
            )
    if enable_adzuna:
        if adzuna.has_credentials():
            sources_active.append("adzuna")
        else:
            warnings.append(
                "🌍 Adzuna désactivé : ajoute ADZUNA_APP_ID et ADZUNA_APP_KEY "
                "(inscription gratuite, 1000 req/mois sur https://developer.adzuna.com/)."
            )
    if enable_companies_watcher:
        sources_active.append("companies_watcher")

    if not sources_active:
        return {
            "jobs": [],
            "by_source": {},
            "warnings": warnings + ["Aucune source disponible. Ajoute au moins une clé API."],
            "summary": "Aucune source disponible.",
        }

    report(0.05, f"📡 Lancement parallèle : {' · '.join(sources_active)}")

    # 3. Lancement parallèle des sources actives
    bus = _ProgressBus(
        progress_callback,
        slots=[
            0.5 if "france_travail" in sources_active else 0.0,
            0.3 if "adzuna" in sources_active else 0.0,
            0.2 if "companies_watcher" in sources_active else 0.0,
        ],
    )

    by_source: Dict[str, List[Dict]] = {s: [] for s in sources_active}

    def _run_ft():
        if "france_travail" not in sources_active:
            return
        def cb(_p, msg):
            bus.update(0, _p, msg)
        bus.update(0, 0.05, "🇫🇷 France Travail · démarrage")
        results = france_travail.search(
            rome_codes=rome_codes,
            departments=departments or None,
            type_contrat="CDI",
            publiee_depuis=publiee_depuis,
            max_per_query=max_per_query,
            progress_callback=cb,
            should_stop=should_stop,
        )
        by_source["france_travail"] = results
        bus.update(0, 1.0, f"🇫🇷 France Travail · {len(results)} offres")

    def _run_adzuna():
        if "adzuna" not in sources_active:
            return
        def cb(_p, msg):
            bus.update(1, _p, msg)
        bus.update(1, 0.05, "🌍 Adzuna · démarrage")
        # Limite à 6 mots-clés max pour Adzuna (quota 1000/mois)
        adzuna_keywords = keywords[:6] if keywords else ["ingénieur simulation"]
        results = adzuna.search(
            keywords=adzuna_keywords,
            locations=None,  # national, on filtre côté config si besoin
            max_days_old=publiee_depuis,
            results_per_query=50,
            progress_callback=cb,
            should_stop=should_stop,
        )
        by_source["adzuna"] = results
        bus.update(1, 1.0, f"🌍 Adzuna · {len(results)} offres")

    def _run_watcher():
        if "companies_watcher" not in sources_active:
            return
        def cb(_p, msg):
            bus.update(2, _p, msg)
        bus.update(2, 0.05, "🎯 Companies Watcher · démarrage")
        # Le watcher filtre par mots-clés (base + extra utilisateur + expansion LLM
        # éventuelle) → cohérent avec ce que promet l'UI ("mots-clés additionnels
        # ciblent Adzuna et Companies Watcher").
        watcher_keywords = keywords if keywords else None
        results = companies_watcher.search(
            keywords=watcher_keywords,
            selected_categories=selected_categories,
            only_france=True,
            progress_callback=cb,
            should_stop=should_stop,
        )
        by_source["companies_watcher"] = results
        bus.update(2, 1.0, f"🎯 Companies Watcher · {len(results)} offres")

    pool = ThreadPoolExecutor(max_workers=3)
    futures = [
        pool.submit(_run_ft),
        pool.submit(_run_adzuna),
        pool.submit(_run_watcher),
    ]
    try:
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                print(f"   ⚠️  Source error: {exc}")
            # Sortie anticipée : si l'utilisateur a demandé l'arrêt, on n'attend
            # pas les futures restantes (les requêtes HTTP en cours finiront
            # rapidement grâce aux timeouts par requête).
            if stopped():
                break
    finally:
        # cancel_futures=True (Python ≥3.9) annule les futures non démarrées.
        pool.shutdown(wait=False, cancel_futures=True)

    if stopped():
        all_jobs = []
        for jobs in by_source.values():
            all_jobs.extend(jobs)
        return {
            "jobs": all_jobs,
            "by_source": {k: len(v) for k, v in by_source.items()},
            "warnings": warnings,
            "summary": f"⏸️ Interrompu · {len(all_jobs)} offres collectées",
        }

    # 4. Agrégation et déduplication
    raw: List[Dict] = []
    for jobs in by_source.values():
        raw.extend(jobs)

    if not raw:
        return {
            "jobs": [],
            "by_source": {k: 0 for k in sources_active},
            "warnings": warnings + ["Aucune offre collectée. Vérifie les clés API ou réessaie plus tard."],
            "summary": "0 offre trouvée.",
        }

    report(0.70, f"🔄 Déduplication ({len(raw)} brut)…")
    unique = deduplicate_smart(raw)
    report(0.74, f"✅ {len(unique)} offres uniques")

    # 5. Scoring heuristique
    report(0.78, "⭐ Scoring heuristique…")
    scored = [score_job(j, profile, config) for j in unique]

    # 6. Re-rank IA (top 25)
    if use_llm_rerank and has_gemini() and scored and not stopped():
        report(0.85, "🧠 Re-classement IA (Gemini)…")
        scored = llm_rerank_top(scored, profile, top_n=25)

    # 7. Extraction de compétences (top 15)
    if use_llm_skills and has_gemini() and scored and not stopped():
        report(0.92, "🔍 Extraction des compétences clés (Gemini)…")
        scored = llm_extract_skills(scored, top_n=15)

    # 8. Filtre min_score + fallback top-25
    min_score = int((config.get("filters") or {}).get("min_score", 20))
    qualified = [j for j in scored if j.get("fit_score", 0) >= min_score]
    if not qualified and scored:
        qualified = sorted(scored, key=lambda x: x.get("fit_score", 0), reverse=True)[:25]

    qualified.sort(key=lambda x: x.get("fit_score", 0), reverse=True)

    by_source_count = {k: len(v) for k, v in by_source.items()}
    summary_parts = [f"{k}={v}" for k, v in by_source_count.items() if v]
    summary = f"✅ {len(qualified)} offres qualifiées · " + " · ".join(summary_parts)

    report(1.0, summary)

    return {
        "jobs": qualified,
        "by_source": by_source_count,
        "warnings": warnings,
        "summary": summary,
    }
