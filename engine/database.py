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
        journal_mode = conn.execute("PRAGMA journal_mode=WAL;").fetchone()
        if not journal_mode or str(journal_mode[0]).lower() != "wal":
            current_mode = journal_mode[0] if journal_mode else "unknown"
            conn.close()
            raise sqlite3.OperationalError(
                f"Unable to enable SQLite WAL journal mode, currently using: {current_mode}"
            )
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
                "vault_path": "TEXT"
            }
            for col, col_type in new_cols.items():
                if col not in columns:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
                    
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score  ON jobs(fit_score)")
            conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        d = dict(row)
        for field in ("matched_skills", "required_skills"):
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
        """Insère ou met à jour les offres. Retourne le nombre de nouvelles offres."""
        new_count = 0
        with self._connect() as conn:
            for job in jobs:
                job_id = (
                    job.get("id")
                    or f"JOB-{abs(hash(job.get('title', '') + job.get('company', '')))}"
                )
                existing = conn.execute(
                    "SELECT id FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()

                ms_json = json.dumps(job.get("matched_skills", []), ensure_ascii=False)
                rs_json = json.dumps(job.get("required_skills", []), ensure_ascii=False)

                if existing is None:
                    conn.execute(
                        """INSERT INTO jobs
                           (id, title, company, location, description, url, source,
                            fit_score, matched_skills, required_skills, status,
                            sourcing_date, created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,'new',?,datetime('now'),datetime('now'))""",
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
                        ),
                    )
                    new_count += 1
                else:
                    conn.execute(
                        """UPDATE jobs SET
                               fit_score       = ?,
                               matched_skills  = ?,
                               required_skills = ?,
                               description     = COALESCE(NULLIF(?, ''), description),
                               url             = COALESCE(NULLIF(?, ''), url),
                               updated_at      = datetime('now')
                           WHERE id = ?""",
                        (
                            int(job.get("fit_score", 0)),
                            ms_json,
                            rs_json,
                            job.get("description", ""),
                            job.get("url", ""),
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
