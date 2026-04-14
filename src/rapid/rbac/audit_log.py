import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from rapid.config import AUDIT_DB_PATH
from typing import Optional

class AuditLog:
    """
    Append-only SQLite audit trail.
    Every query writes a record regardless of routing outcome.
    Records cannot be modified after writing — only inserted.
    """

    def __init__(self, db_path: str = AUDIT_DB_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT NOT NULL,
                    user_id     TEXT NOT NULL,
                    user_role   TEXT NOT NULL,
                    query_text  TEXT NOT NULL,
                    project_id  TEXT,
                    departments_accessed TEXT,
                    access_verdict      TEXT NOT NULL,
                    denial_reason       TEXT,
                    confidence_score    REAL,
                    confidence_verdict  TEXT,
                    routing_path        TEXT,
                    model_used          TEXT,
                    latency_ms          INTEGER
                )
            """)
            # Migration: add new columns safely (ignored if they already exist)
            cursor = conn.cursor()
            for col, typedef in [
                ("db_triggered",      "BOOLEAN DEFAULT 0"),
                ("rag_triggered",     "BOOLEAN DEFAULT 1"),
                ("firewall_applied",  "BOOLEAN DEFAULT 1"),
                ("raw_data_destroyed","BOOLEAN DEFAULT 1"),
                ("columns_blocked",   "TEXT DEFAULT '[]'"),
                ("columns_anonymized","TEXT DEFAULT '[]'"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {typedef}")
                except sqlite3.OperationalError:
                    pass  # column already exists — safe to ignore
            conn.commit()

    def log(
        self,
        user_id: str,
        user_role: str,
        query_text: str,
        access_verdict: str,           # "PERMITTED" or "DENIED"
        project_id: Optional[str] = None,
        departments_accessed: Optional[list] = None,
        denial_reason: Optional[str] = None,
        confidence_score: Optional[float] = None,
        confidence_verdict: Optional[str] = None,
        routing_path: Optional[str] = None,
        model_used: Optional[str] = None,
        latency_ms: Optional[int] = None,
        db_triggered: bool = False,
        rag_triggered: bool = True,
        firewall_applied: bool = True,
        raw_data_destroyed: bool = True,
        columns_blocked: Optional[list] = None,
        columns_anonymized: Optional[list] = None,
    ):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_log (
                    timestamp, user_id, user_role, query_text, project_id,
                    departments_accessed, access_verdict, denial_reason,
                    confidence_score, confidence_verdict, routing_path,
                    model_used, latency_ms,
                    db_triggered, rag_triggered, firewall_applied,
                    raw_data_destroyed, columns_blocked, columns_anonymized
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                user_id,
                user_role,
                query_text,
                project_id,
                json.dumps(departments_accessed) if departments_accessed else None,
                access_verdict,
                denial_reason,
                confidence_score,
                confidence_verdict,
                routing_path,
                model_used,
                latency_ms,
                int(db_triggered),
                int(rag_triggered),
                int(firewall_applied),
                int(raw_data_destroyed),
                json.dumps(columns_blocked or []),
                json.dumps(columns_anonymized or []),
            ))
            conn.commit()

    def get_recent(self, limit: int = 50) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def export_csv(self, path: str):
        import csv
        rows = self.get_recent(limit=10000)
        if not rows:
            return
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
