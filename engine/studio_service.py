"""
Studio service layer — logique métier extraite de Dashboard.py.

Contient les trois fonctions de service du bloc "Édition assistée" :

* :func:`_init_gen_state`          — initialisation de l'état de génération
* :func:`save_final_candidate_version` — recompilation + archivage version finale
* :func:`mark_application_as_sent`     — marquage DB "candidature envoyée"

Toutes les dépendances externes (base de données, système de fichiers, moteur
de génération) sont passées explicitement, ce qui facilite les tests unitaires
et évite tout couplage avec le module Dashboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def _init_gen_state(gen_state: dict, profile: dict, job: dict) -> dict:
    """Initialise les clés obligatoires de *gen_state* si elles sont absentes.

    * ``letter_text`` : pré-rempli par heuristique (sans appel LLM).
    * ``section_overrides`` : dict vide par défaut.

    Modifie *gen_state* en place et le retourne.
    """
    if not gen_state.get("letter_text"):
        try:
            from Pipeline import generate_cover_letter_heuristic  # type: ignore[import]
            gen_state["letter_text"] = generate_cover_letter_heuristic(profile, job)
        except Exception:
            gen_state.setdefault("letter_text", "")
    gen_state.setdefault("section_overrides", {})
    return gen_state


def save_final_candidate_version(
    job_id: str,
    job: dict,
    gen_state: dict,
    photo_path: str | None,
    *,
    db,
    root: Path,
    generate_documents_fn: Callable,
    safe_filename_fn: Callable[[str], str],
) -> dict:
    """Recompile le CV avec les éditions courantes, persiste la lettre sur
    disque, puis archive les versions finales (CV + lettre) en base.

    Modifie *gen_state* en place (``cv_path``, ``cv_data``, ``letter_path``)
    et le retourne.  Toute exception est propagée au caller, qui reste
    responsable de l'affichage d'erreur et de la gestion de l'état Streamlit.

    Args:
        job_id: Identifiant de l'offre.
        job: Dict de l'offre (title, company, …).
        gen_state: État courant de génération (modifié en place).
        photo_path: Chemin absolu de la photo de profil, ou None.
        db: Instance de :class:`engine.database.JobDatabase`.
        root: Répertoire racine du projet (pour les chemins ``vault/``).
        generate_documents_fn: Callable équivalent à ``Dashboard.generate_documents``.
        safe_filename_fn: Callable équivalent à ``Dashboard.safe_filename``.
    """
    result = generate_documents_fn(
        job, gen_cv=True, gen_letter=False, use_llm=False,
        section_overrides=gen_state.get("section_overrides") or {},
        photo_path=photo_path,
    )
    gen_state["cv_path"] = result.get("cv_path", "") or gen_state.get("cv_path", "")
    cv_res = result.get("cv_result") or {}
    if cv_res.get("cv_data"):
        gen_state["cv_data"] = cv_res["cv_data"]

    if gen_state.get("letter_text"):
        out_dir = root / "vault" / safe_filename_fn(
            f"{job.get('company', 'job')}_{job.get('title', 'cv')}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        lp = out_dir / "lettre.txt"
        lp.write_text(gen_state["letter_text"], encoding="utf-8")
        gen_state["letter_path"] = str(lp)

    final_cv_data = gen_state.get("cv_data") or {}
    db.save_resume_version(
        job_id=job_id,
        headline=final_cv_data.get("headline", ""),
        summary=final_cv_data.get("summary", ""),
        cv_path=gen_state.get("cv_path", ""),
        is_final=True,
        notes="Validée finale par l'utilisateur",
    )
    if gen_state.get("letter_text"):
        db.save_cover_letter_version(
            job_id=job_id,
            letter_text=gen_state.get("letter_text", ""),
            letter_path=gen_state.get("letter_path", ""),
            is_final=True,
            notes="Validée finale par l'utilisateur",
        )
    return gen_state


def mark_application_as_sent(job_id: str, gen_state: dict, *, db) -> None:
    """Marque la candidature comme envoyée en base de données.

    La purge de l'état Streamlit reste à la charge du caller (code UI),
    ce qui évite toute incohérence si l'appel DB échoue.

    Args:
        job_id: Identifiant de l'offre.
        gen_state: État courant de génération (lecture seule dans cette fonction).
        db: Instance de :class:`engine.database.JobDatabase`.
    """
    final_cv_data = gen_state.get("cv_data") or {}
    db.mark_as_sent(
        job_id=job_id,
        via="manual",
        edited_headline=final_cv_data.get("headline", ""),
        edited_summary=final_cv_data.get("summary", ""),
        vault_path=gen_state.get("cv_path") or gen_state.get("letter_path"),
    )
