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
    persona: str = "Industrial",
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
        persona: Persona utilisé pour la génération (Research, Industrial, Startup).
        db: Instance de :class:`engine.database.JobDatabase`.
        root: Répertoire racine du projet (pour les chemins ``vault/``).
        generate_documents_fn: Callable équivalent à ``Dashboard.generate_documents``.
        safe_filename_fn: Callable équivalent à ``Dashboard.safe_filename``.
    """
    from engine.schemas import CVGenState
    try:
        CVGenState.model_validate(gen_state)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"GenState struct errors: {e}")
    result = generate_documents_fn(
        job, gen_cv=True, gen_letter=False, use_llm=False,
        section_overrides=gen_state.get("section_overrides") or {},
        photo_path=photo_path,
        persona=persona,
    )
    gen_state["cv_path"] = result.get("cv_path", "") or gen_state.get("cv_path", "")
    cv_res = result.get("cv_result") or {}
    if cv_res.get("cv_data"):
        gen_state["cv_data"] = cv_res["cv_data"]
    if result.get("llm_name"):
        gen_state["llm_name"] = result["llm_name"]

    if gen_state.get("letter_text"):
        out_dir = root / "vault" / safe_filename_fn(
            f"{job.get('company', 'job')}_{job.get('title', 'cv')}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        # Tenter le rendu PDF via Typst
        try:
            from engine.letter_renderer import LetterRenderer, build_letter_data
            import re as _re

            renderer = LetterRenderer()
            letter_text = gen_state["letter_text"]
            # Extraire les paragraphes du corps
            raw_paragraphs = [
                p.strip() for p in _re.split(r"\n\s*\n", letter_text)
                if p.strip()
                and not p.strip().startswith("Objet")
                and not p.strip().startswith("Madame")
                and "salutations" not in p.lower()
                and "@" not in p
                and not _re.match(r"^\+?\d", p.strip())
                and not _re.match(r"^\d{2}/\d{2}/\d{4}$", p.strip())
            ]
            paragraphs = raw_paragraphs if raw_paragraphs else [letter_text]

            # Charger le profil pour build_letter_data
            import json as _json
            profile_path = root / "profiles" / "master_profile.json"
            profile = {}
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as _f:
                    profile = _json.load(_f)

            letter_data = build_letter_data(profile, job, paragraphs)
            pdf_path = out_dir / "lettre.pdf"
            pdf_result = renderer.render(letter_data, pdf_path)
            if pdf_result and pdf_result.exists():
                gen_state["letter_path"] = str(pdf_result)
            else:
                # Fallback texte
                lp = out_dir / "lettre.txt"
                lp.write_text(gen_state["letter_text"], encoding="utf-8")
                gen_state["letter_path"] = str(lp)
        except Exception:
            lp = out_dir / "lettre.txt"
            lp.write_text(gen_state["letter_text"], encoding="utf-8")
            gen_state["letter_path"] = str(lp)

        # Toujours sauvegarder le fallback texte
        txt_fallback = out_dir / "lettre.txt"
        if not txt_fallback.exists():
            txt_fallback.write_text(gen_state["letter_text"], encoding="utf-8")

    final_cv_data = gen_state.get("cv_data") or {}
    
    # [KARPATHY DATA FLYWHEEL] Log the human preference data!
    try:
        from engine.data_engine import data_engine
        raw_llm_proposal = gen_state.get("section_proposal", {})
        if raw_llm_proposal and final_cv_data:
            data_engine.log_user_correction(job, raw_llm_proposal, final_cv_data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Data engine tracking failed: {e}")

    # [KARPATHY AUTO EVAL] Score the final output against the job description
    try:
        from engine.evaluator import AutoEval
        eval_metrics = AutoEval.evaluate_cv_fit(final_cv_data, job)
        notes = f"Validée finale par l'utilisateur. Recall Score: {eval_metrics['score']}%. "
        if eval_metrics['missing_keywords']:
            notes += f"Mots clés manquants: {', '.join(eval_metrics['missing_keywords'])}"
    except Exception as e:
        notes = "Validée finale par l'utilisateur"

    db.save_resume_version(
        job_id=job_id,
        headline=final_cv_data.get("headline", ""),
        summary=final_cv_data.get("summary", ""),
        cv_path=gen_state.get("cv_path", ""),
        is_final=True,
        notes=notes,
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
        model=gen_state.get("llm_name"),
    )
