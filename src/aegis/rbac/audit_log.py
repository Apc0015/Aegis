import sqlite3
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from aegis.config import AUDIT_DB_PATH
from typing import Optional

logger = logging.getLogger(__name__)

class AuditAlerter:
    """
    Monitors audit_log for suspicious patterns and logs warnings.

    Checks triggered after each log() call:
    1. Frequency alert: same user queries > FREQ_THRESHOLD times in FREQ_WINDOW_MINUTES
    2. Denied access spike: > DENIED_THRESHOLD denied queries from same user in window
    3. Sensitive keyword alert: query contains salary/SSN/PII keywords AND role != admin
    4. Low confidence spam: > 5 low-confidence results in a row for same user
    """

    FREQ_THRESHOLD = 20
    FREQ_WINDOW_MINUTES = 10
    DENIED_THRESHOLD = 5
    LOW_CONF_STREAK_THRESHOLD = 5
    SENSITIVE_KEYWORDS = {
        "salary",
        "ssn",
        "social security",
        "compensation",
        "personal email",
        "date of birth",
    }

    def __init__(self):
        # Deques store UTC timestamps (as float epoch seconds) for time-windowed counting
        self._query_times: defaultdict[str, deque] = defaultdict(deque)
        self._denied_times: defaultdict[str, deque] = defaultdict(deque)
        # Track consecutive low-confidence verdicts per user
        self._low_conf_streak: defaultdict[str, int] = defaultdict(int)

    def _prune_window(self, dq: deque, window_seconds: float, now: float) -> None:
        """Remove entries older than the sliding time window."""
        cutoff = now - window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def alert(
        self,
        user_id: str,
        user_role: str,
        query_text: str,
        access_verdict: str,
        confidence_verdict: Optional[str] = None,
    ) -> None:
        """
        Evaluate all alert conditions and emit logger.warning messages when triggered.
        Called at the end of AuditLog.log().
        """
        now = datetime.now(timezone.utc).timestamp()
        window_seconds = self.FREQ_WINDOW_MINUTES * 60

        # --- 1. Frequency alert ---
        dq_queries = self._query_times[user_id]
        self._prune_window(dq_queries, window_seconds, now)
        dq_queries.append(now)
        if len(dq_queries) > self.FREQ_THRESHOLD:
            logger.warning(
                "[SECURITY ALERT] High query frequency: user=%s submitted %d queries "
                "in the last %d minutes (threshold=%d).",
                user_id,
                len(dq_queries),
                self.FREQ_WINDOW_MINUTES,
                self.FREQ_THRESHOLD,
            )

        # --- 2. Denied access spike ---
        if access_verdict == "DENIED":
            dq_denied = self._denied_times[user_id]
            self._prune_window(dq_denied, window_seconds, now)
            dq_denied.append(now)
            if len(dq_denied) > self.DENIED_THRESHOLD:
                logger.warning(
                    "[SECURITY ALERT] Denied access spike: user=%s has been denied %d times "
                    "in the last %d minutes (threshold=%d).",
                    user_id,
                    len(dq_denied),
                    self.FREQ_WINDOW_MINUTES,
                    self.DENIED_THRESHOLD,
                )

        # --- 3. Sensitive keyword alert ---
        if user_role != "admin":
            query_lower = query_text.lower()
            for kw in self.SENSITIVE_KEYWORDS:
                if kw in query_lower:
                    logger.warning(
                        "[SECURITY ALERT] Sensitive keyword detected: user=%s (role=%s) "
                        "queried for '%s'. Query: %.120r",
                        user_id,
                        user_role,
                        kw,
                        query_text,
                    )
                    break  # one warning per query is enough

        # --- 4. Low confidence spam ---
        if confidence_verdict == "low":
            self._low_conf_streak[user_id] += 1
            if self._low_conf_streak[user_id] > self.LOW_CONF_STREAK_THRESHOLD:
                logger.warning(
                    "[SECURITY ALERT] Low confidence spam: user=%s has received %d consecutive "
                    "low-confidence results (threshold=%d).",
                    user_id,
                    self._low_conf_streak[user_id],
                    self.LOW_CONF_STREAK_THRESHOLD,
                )
        else:
            # Reset streak on any non-low result
            self._low_conf_streak[user_id] = 0


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
        self._alerter = AuditAlerter()

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

        # Run alert checks after the record is safely persisted
        self._alerter.alert(
            user_id=user_id,
            user_role=user_role,
            query_text=query_text,
            access_verdict=access_verdict,
            confidence_verdict=confidence_verdict,
        )

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
