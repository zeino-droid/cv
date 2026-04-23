"""
engine/database.py
Gestion de la base de données SQLite pour le suivi des candidatures.
Supporte le versioning des CV et lettres de motivation générés.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = os.environ.get("CV_DB_PATH", "candidatures.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialise toutes les tables nécessaires."""
    conn = get_connection()
    c = conn.cursor()

    # Table principale des candidatures
    c.execute("""
        CREATE TABLE IF NOT EXISTS candidatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            entreprise TEXT,
            poste TEXT,
            url_offre TEXT,
            statut TEXT DEFAULT 'nouvelle',
            date_creation TEXT,
            date_modification TEXT,
            job_offer_json TEXT,
            notes TEXT
        )
    """)

    # Table des versions de CV
    c.execute("""
        CREATE TABLE IF NOT EXISTS resume_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            cv_content_json TEXT,
            cv_typst_source TEXT,
            cv_pdf_path TEXT,
            is_final INTEGER DEFAULT 0,
            created_at TEXT,
            notes TEXT,
            FOREIGN KEY (job_id) REFERENCES candidatures(job_id)
        )
    """)

    # Table des versions de lettres
    c.execute("""
        CREATE TABLE IF NOT EXISTS cover_letter_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            letter_text TEXT,
            letter_typst_source TEXT,
            letter_pdf_path TEXT,
            is_final INTEGER DEFAULT 0,
            created_at TEXT,
            notes TEXT,
            FOREIGN KEY (job_id) REFERENCES candidatures(job_id)
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Candidatures
# ---------------------------------------------------------------------------

def upsert_candidature(job_offer: dict, job_id: str, statut: str = "en_cours") -> str:
    """Crée ou met à jour une candidature."""
    init_db()
    conn = get_connection()
    c = conn.cursor()
    now = datetime.now().isoformat()

    c.execute("""
        INSERT INTO candidatures
            (job_id, entreprise, poste, url_offre, statut, date_creation, date_modification, job_offer_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            statut = excluded.statut,
            date_modification = excluded.date_modification,
            job_offer_json = excluded.job_offer_json
    """, (
        job_id,
        job_offer.get("entreprise", job_offer.get("company", "")),
        job_offer.get("titre", job_offer.get("title", "")),
        job_offer.get("url", ""),
        statut,
        now,
        now,
        json.dumps(job_offer, ensure_ascii=False),
    ))

    conn.commit()
    conn.close()
    return job_id


def get_candidature(job_id: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    row = c.execute(
        "SELECT * FROM candidatures WHERE job_id = ?", (job_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_candidatures() -> List[Dict]:
    init_db()
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM candidatures ORDER BY date_modification DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_candidature_statut(job_id: str, statut: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE candidatures SET statut = ?, date_modification = ? WHERE job_id = ?",
        (statut, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def update_candidature_url(job_id: str, new_url: str):
    """Met à jour l'URL de l'offre (lien de secours)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE candidatures SET url_offre = ?, date_modification = ? WHERE job_id = ?",
        (new_url, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Versions CV
# ---------------------------------------------------------------------------

def save_resume_version(
    job_id: str,
    cv_content: dict,
    cv_typst: str = "",
    cv_pdf_path: str = "",
    is_final: bool = False,
    notes: str = "",
) -> int:
    """
    Sauvegarde une version du CV pour un job donné.
    Retourne l'ID de la version créée.
    """
    init_db()
    conn = get_connection()
    c = conn.cursor()

    # Numéro de version auto-incrémenté
    row = c.execute(
        "SELECT MAX(version) as max_v FROM resume_versions WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    next_version = (row["max_v"] or 0) + 1

    # Si final, désactiver les anciennes versions finales
    if is_final:
        c.execute(
            "UPDATE resume_versions SET is_final = 0 WHERE job_id = ?",
            (job_id,),
        )

    c.execute("""
        INSERT INTO resume_versions
            (job_id, version, cv_content_json, cv_typst_source, cv_pdf_path, is_final, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        next_version,
        json.dumps(cv_content, ensure_ascii=False),
        cv_typst,
        cv_pdf_path,
        1 if is_final else 0,
        datetime.now().isoformat(),
        notes,
    ))

    version_id = c.lastrowid
    conn.commit()
    conn.close()
    return version_id


def get_resume_versions(job_id: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM resume_versions WHERE job_id = ? ORDER BY version DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_final_resume(job_id: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    row = c.execute(
        "SELECT * FROM resume_versions WHERE job_id = ? AND is_final = 1 ORDER BY version DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Versions Lettre de Motivation
# ---------------------------------------------------------------------------

def save_cover_letter_version(
    job_id: str,
    letter_text: str,
    letter_typst: str = "",
    letter_pdf_path: str = "",
    is_final: bool = False,
    notes: str = "",
) -> int:
    """
    Sauvegarde une version de la lettre de motivation.
    Retourne l'ID de la version créée.
    """
    init_db()
    conn = get_connection()
    c = conn.cursor()

    row = c.execute(
        "SELECT MAX(version) as max_v FROM cover_letter_versions WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    next_version = (row["max_v"] or 0) + 1

    if is_final:
        c.execute(
            "UPDATE cover_letter_versions SET is_final = 0 WHERE job_id = ?",
            (job_id,),
        )

    c.execute("""
        INSERT INTO cover_letter_versions
            (job_id, version, letter_text, letter_typst_source, letter_pdf_path, is_final, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_id,
        next_version,
        letter_text,
        letter_typst,
        letter_pdf_path,
        1 if is_final else 0,
        datetime.now().isoformat(),
        notes,
    ))

    version_id = c.lastrowid
    conn.commit()
    conn.close()
    return version_id


def get_cover_letter_versions(job_id: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM cover_letter_versions WHERE job_id = ? ORDER BY version DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_final_cover_letter(job_id: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    row = c.execute(
        "SELECT * FROM cover_letter_versions WHERE job_id = ? AND is_final = 1 ORDER BY version DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Stats pour l'onglet Archives
# ---------------------------------------------------------------------------

def get_archive_stats() -> Dict:
    """Statistiques globales pour l'onglet Archives."""
    init_db()
    conn = get_connection()
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM candidatures").fetchone()[0]
    par_statut = c.execute(
        "SELECT statut, COUNT(*) as n FROM candidatures GROUP BY statut"
    ).fetchall()
    total_cv = c.execute("SELECT COUNT(*) FROM resume_versions WHERE is_final = 1").fetchone()[0]
    total_letters = c.execute("SELECT COUNT(*) FROM cover_letter_versions WHERE is_final = 1").fetchone()[0]

    conn.close()
    return {
        "total_candidatures": total,
        "par_statut": {r["statut"]: r["n"] for r in par_statut},
        "cv_finaux": total_cv,
        "lettres_finales": total_letters,
    }
