"""
Base de données SQLite — Jobs + Applications
Remplace tracker.csv avec une vraie DB persistante
"""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("storage/jobs.db")

VALID_STATUSES = [
    "new",
    "selected",
    "generated",
    "sent",
    "applied",
    "interview",
    "offer",
    "rejected",
    "ignored",
]

STATUS_EMOJI = {
    "new": "🆕",
    "selected": "⭐",
    "generated": "📄",
    "sent": "📤",
    "applied": "✅",
    "interview": "🎤",
    "offer": "🎉",
    "rejected": "❌",
    "ignored": "🚫",
}


class JobDatabase:
    def __init__(self, db_path: str = "storage/jobs.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            pragma_result = conn.execute("PRAGMA journal_mode=WAL;").fetchone()
            current_mode = pragma_result[0] if pragma_result else "unknown"
            if str(current_mode).lower() != "wal":
                raise sqlite3.OperationalError(
                    "Unable to enable SQLite WAL journal mode, "
                    f"currently using: {current_mode}. Check filesystem/permissions compatibility."
                )
        except Exception:
            conn.close()
            raise
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id              TEXT PRIMARY KEY,
                    title           TEXT NOT NULL,
                    company         TEXT,
                    location        TEXT,
                    description     TEXT,
                    url             TEXT,
                    source          TEXT,
                    fit_score       INTEGER DEFAULT 0,
                    matched_skills  TEXT,
                    required_skills TEXT,
                    status          TEXT DEFAULT 'new',
                    notes           TEXT,
                    cv_path         TEXT,
                    letter_path     TEXT,
                    sourcing_date   TEXT,
                    applied_date    TEXT,
                    response_date   TEXT,
                    created_at      TEXT DEFAULT (datetime('now')),
                    updated_at      TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # Migration chirurgicale pour les colonnes Phase 3
            cursor = conn.execute("PRAGMA table_info(jobs)")
            columns = [row[1] for row in cursor.fetchall()]
            new_cols = {
                "sent_via": "TEXT",
                "sent_at": "TEXT",
                "final_headline": "TEXT",
                "final_summary": "TEXT",
                "vault_path": "TEXT",
                "ai_score": "INTEGER",
                "ai_reason": "TEXT",
                "extracted_skills": "TEXT",
                "posted_date": "TEXT",
            }
            for col, col_type in new_cols.items():
                if col not in columns:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
                    
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score  ON jobs(fit_score)")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS resume_versions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id       TEXT NOT NULL,
                    version      INTEGER DEFAULT 1,
                    headline     TEXT,
                    summary      TEXT,
                    cv_path      TEXT,
                    is_final     INTEGER DEFAULT 0,
                    created_at   TEXT DEFAULT (datetime('now')),
                    notes        TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cover_letter_versions (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id       TEXT NOT NULL,
                    version      INTEGER DEFAULT 1,
                    letter_text  TEXT,
                    letter_path  TEXT,
                    is_final     INTEGER DEFAULT 0,
                    created_at   TEXT DEFAULT (datetime('now')),
                    notes        TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rv_job ON resume_versions(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_lv_job ON cover_letter_versions(job_id)")
            conn.commit()

    def save_resume_version(
        self,
        job_id: str,
        headline: str = "",
        summary: str = "",
        cv_path: str = "",
        is_final: bool = False,
        notes: str = "",
    ) -> int:
        """Sauvegarde une version numérotée du CV pour un job."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS mv FROM resume_versions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            next_v = int(row["mv"] or 0) + 1
            if is_final:
                conn.execute(
                    "UPDATE resume_versions SET is_final = 0 WHERE job_id = ?",
                    (job_id,),
                )
            cur = conn.execute(
                """INSERT INTO resume_versions
                   (job_id, version, headline, summary, cv_path, is_final, created_at, notes)
                   VALUES (?,?,?,?,?,?,datetime('now'),?)""",
                (job_id, next_v, headline, summary, cv_path,
                 1 if is_final else 0, notes),
            )
            conn.commit()
            return cur.lastrowid or 0

    def save_cover_letter_version(
        self,
        job_id: str,
        letter_text: str = "",
        letter_path: str = "",
        is_final: bool = False,
        notes: str = "",
    ) -> int:
        """Sauvegarde une version numérotée de la lettre pour un job."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS mv FROM cover_letter_versions WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            next_v = int(row["mv"] or 0) + 1
            if is_final:
                conn.execute(
                    "UPDATE cover_letter_versions SET is_final = 0 WHERE job_id = ?",
                    (job_id,),
                )
            cur = conn.execute(
                """INSERT INTO cover_letter_versions
                   (job_id, version, letter_text, letter_path, is_final, created_at, notes)
                   VALUES (?,?,?,?,?,datetime('now'),?)""",
                (job_id, next_v, letter_text, letter_path,
                 1 if is_final else 0, notes),
            )
            conn.commit()
            return cur.lastrowid or 0

    def get_resume_versions(self, job_id: str) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM resume_versions WHERE job_id = ? ORDER BY version DESC",
                (job_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_cover_letter_versions(self, job_id: str) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM cover_letter_versions WHERE job_id = ? ORDER BY version DESC",
                (job_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        for field in ("matched_skills", "required_skills", "extracted_skills"):
            raw = d.get(field)
            if raw:
                try:
                    d[field] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            else:
                d[field] = []
        return d

    def upsert_jobs(self, jobs: List[Dict]) -> int:
        """Insère ou met à jour les offres. Retourne le nombre de nouvelles offres.
        
        V2 : Inclut une vérification fuzzy (titre+entreprise) pour éviter les doublons
        qui arrivent avec des IDs légèrement différents entre les sources/sessions.
        """
        new_count = 0
        with self._connect() as conn:
            # Pré-charger les titres+entreprises existants pour la dédup fuzzy
            existing_signatures = {}
            try:
                rows = conn.execute("SELECT id, title, company FROM jobs").fetchall()
                for row in rows:
                    title_tokens = set((row["title"] or "").lower().split())
                    company_lower = (row["company"] or "").lower().strip()
                    existing_signatures[row["id"]] = (title_tokens, company_lower)
            except Exception:
                pass

            for job in jobs:
                job_id = (
                    job.get("id")
                    or f"JOB-{abs(hash(job.get('title', '') + job.get('company', '')))}"
                )
                existing = conn.execute(
                    "SELECT id FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()

                # V2 : Vérification fuzzy — si le job n'existe pas par ID,
                # vérifier par titre+entreprise similaire (Jaccard > 0.7)
                if existing is None and existing_signatures:
                    new_title_tokens = set((job.get("title") or "").lower().split())
                    new_company = (job.get("company") or "").lower().strip()
                    
                    for ex_id, (ex_tokens, ex_company) in existing_signatures.items():
                        # Même entreprise (ou très similaire)
                        company_match = (
                            new_company == ex_company
                            or new_company in ex_company
                            or ex_company in new_company
                        )
                        if not company_match:
                            continue
                        # Jaccard sur les tokens du titre
                        if new_title_tokens and ex_tokens:
                            inter = len(new_title_tokens & ex_tokens)
                            union = len(new_title_tokens | ex_tokens) or 1
                            if inter / union >= 0.7:
                                # C'est un doublon — on met à jour le score si meilleur
                                new_score = int(job.get("fit_score", 0))
                                conn.execute(
                                    "UPDATE jobs SET fit_score = MAX(fit_score, ?), updated_at = datetime('now') WHERE id = ?",
                                    (new_score, ex_id),
                                )
                                existing = True  # Flag pour skip l'insert
                                break

                ms_json = json.dumps(job.get("matched_skills", []), ensure_ascii=False)
                rs_json = json.dumps(job.get("required_skills", []), ensure_ascii=False)
                es_json = json.dumps(job.get("extracted_skills", []), ensure_ascii=False)
                ai_score_val = job.get("ai_score")
                ai_score_int = int(ai_score_val) if ai_score_val is not None else None
                ai_reason = job.get("ai_reason") or None
                posted_date = job.get("posted_date") or None

                if existing is None:
                    conn.execute(
                        """INSERT INTO jobs
                           (id, title, company, location, description, url, source,
                            fit_score, matched_skills, required_skills, status,
                            sourcing_date, ai_score, ai_reason, extracted_skills, posted_date,
                            created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,'new',?,?,?,?,?,datetime('now'),datetime('now'))""",
                        (
                            job_id,
                            job.get("title", ""),
                            job.get("company", ""),
                            job.get("location", ""),
                            job.get("description", ""),
                            job.get("url", ""),
                            job.get("source", ""),
                            int(job.get("fit_score", 0)),
                            ms_json,
                            rs_json,
                            job.get("sourcing_date") or date.today().isoformat(),
                            ai_score_int,
                            ai_reason,
                            es_json,
                            posted_date,
                        ),
                    )
                    # Ajouter à l'index pour les prochaines itérations
                    title_tokens = set((job.get("title", "")).lower().split())
                    company_lower = (job.get("company", "")).lower().strip()
                    existing_signatures[job_id] = (title_tokens, company_lower)
                    new_count += 1
                elif existing is not True:
                    # existing est un Row (pas le flag True de la dédup fuzzy)
                    conn.execute(
                        """UPDATE jobs SET
                               fit_score        = ?,
                               matched_skills   = ?,
                               required_skills = ?,
                               description     = COALESCE(NULLIF(?, ''), description),
                               url             = COALESCE(NULLIF(?, ''), url),
                               ai_score         = COALESCE(?, ai_score),
                               ai_reason        = COALESCE(NULLIF(?, ''), ai_reason),
                               extracted_skills = CASE WHEN ?='[]' THEN extracted_skills ELSE ? END,
                               posted_date      = COALESCE(NULLIF(?, ''), posted_date),
                               updated_at       = datetime('now')
                           WHERE id = ?""",
                        (
                            int(job.get("fit_score", 0)),
                            ms_json,
                            rs_json,
                            job.get("description", ""),
                            job.get("url", ""),
                            ai_score_int,
                            ai_reason or "",
                            es_json, es_json,
                            posted_date or "",
                            job_id,
                        ),
                    )
            conn.commit()
        return new_count

    def update_status(self, job_id: str, status: str, notes: str = "") -> bool:
        """Met à jour le statut d'une offre."""
        if status not in VALID_STATUSES:
            return False
        extra_sql = ""
        extra_params: List[Any] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        if status in ("sent", "applied"):
            extra_sql = ", applied_date = ?"
            extra_params = [now]
        elif status in ("interview", "offer", "rejected"):
            extra_sql = ", response_date = ?"
            extra_params = [now]
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE jobs SET status=?, notes=?, updated_at=datetime('now'){extra_sql} WHERE id=?",
                [status, notes] + extra_params + [job_id],
            )
            conn.commit()
            return cur.rowcount > 0

    def mark_as_sent(self, job_id: str, via: str, edited_headline: str = None, edited_summary: str = None, vault_path: str = None) -> bool:
        """Marque une offre comme envoyée avec les métadonnées de candidature."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._connect() as conn:
            cur = conn.execute(
                """UPDATE jobs SET 
                   status = 'sent',
                   sent_via = ?,
                   sent_at = ?,
                   applied_date = ?,
                   final_headline = ?,
                   final_summary = ?,
                   vault_path = ?,
                   updated_at = datetime('now')
                   WHERE id = ?""",
                (via, now, now, edited_headline, edited_summary, vault_path, job_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def save_generation(self, job_id: str, cv_path: str, letter_path: str) -> None:
        """Sauvegarde les chemins des documents générés."""
        with self._connect() as conn:
            conn.execute(
                """UPDATE jobs SET
                       cv_path     = ?,
                       letter_path = ?,
                       status      = CASE WHEN status = 'new' THEN 'generated' ELSE status END,
                       updated_at  = datetime('now')
                   WHERE id = ?""",
                (cv_path, letter_path, job_id),
            )
            conn.commit()

    def delete_job(self, job_id: str) -> bool:
        """Supprime définitivement une offre de la base."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_jobs(
        self,
        min_score: int = 0,
        status: Optional[str] = None,
        location_filter: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """Retourne les offres filtrées, triées par score décroissant."""
        q = "SELECT * FROM jobs WHERE fit_score >= ?"
        params: List[Any] = [min_score]
        if status:
            q += " AND status = ?"
            params.append(status)
        if location_filter:
            q += " AND LOWER(location) LIKE ?"
            params.append(f"%{location_filter.lower()}%")
        if search:
            s = f"%{search.lower()}%"
            q += " AND (LOWER(title) LIKE ? OR LOWER(company) LIKE ?)"
            params += [s, s]
        q += " ORDER BY fit_score DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(q, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_stats(self) -> Dict:
        """Statistiques globales de la recherche d'emploi."""
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            rows = conn.execute(
                "SELECT status, COUNT(*) as cnt FROM jobs GROUP BY status"
            ).fetchall()
            by_status = {r["status"]: r["cnt"] for r in rows}
            agg = conn.execute(
                "SELECT AVG(fit_score) as avg_s, MAX(fit_score) as max_s FROM jobs"
            ).fetchone()
            avg_score = round(float(agg["avg_s"] or 0), 1)
            max_score = int(agg["max_s"] or 0)
            today = date.today().isoformat()
            new_today = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE sourcing_date = ? OR created_at LIKE ?",
                (today, f"{today}%"),
            ).fetchone()[0]
        return {
            "total": total,
            "by_status": by_status,
            "avg_score": avg_score,
            "max_score": max_score,
            "new_today": new_today,
            "sent": by_status.get("sent", 0) + by_status.get("applied", 0),
            "interviews": by_status.get("interview", 0),
            "offers": by_status.get("offer", 0),
        }

    def get_top_to_apply(self, n: int = 10) -> List[Dict]:
        """Top N offres à postuler (statut new ou selected)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status IN ('new','selected') ORDER BY fit_score DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_by_location(self) -> List[Dict]:
        """Nombre d'offres par localisation."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT location, COUNT(*) as cnt FROM jobs
                   WHERE location IS NOT NULL AND location != ''
                   GROUP BY location ORDER BY cnt DESC LIMIT 15"""
            ).fetchall()
        return [{"location": r["location"], "cnt": r["cnt"]} for r in rows]
