"""
DB Pipeline — Database Query Pipeline
Supports SQLite, PostgreSQL, and MySQL via env vars:
  AEGIS_DB_TYPE = sqlite | postgres | mysql
  AEGIS_DB_PATH = path/to/file.db          (SQLite only)
  AEGIS_DB_URL  = dialect://user:pass@host/db  (Postgres/MySQL)
"""
import os
import sqlite3
import logging
import re
from aegis.rbac.rbac_module import (
    apply_column_rules,
    apply_column_rules_multi,
    apply_row_filter,
    PERSONAL_TABLES,
)

logger = logging.getLogger(__name__)

DB_TYPE = os.getenv("AEGIS_DB_TYPE", "sqlite").lower()
DB_PATH = os.getenv("AEGIS_DB_PATH", "data/medical_company.db")
DB_URL  = os.getenv("AEGIS_DB_URL", "")

# Module-level cache for introspected schema
_SCHEMA_CACHE: str = ""


def get_readonly_connection():
    """
    Returns a read-only DB connection based on AEGIS_DB_TYPE.
    SQLite  → built-in sqlite3 (mode=ro URI).
    Postgres/MySQL → SQLAlchemy connection (requires sqlalchemy + driver installed).
    """
    if DB_TYPE == "sqlite":
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    if DB_TYPE in ("postgres", "postgresql", "mysql"):
        try:
            from sqlalchemy import create_engine, text as sa_text
        except ImportError:
            raise RuntimeError(
                "sqlalchemy is required for Postgres/MySQL. Run: pip install sqlalchemy"
            )
        if not DB_URL:
            raise RuntimeError(
                "AEGIS_DB_URL must be set for Postgres/MySQL. "
                "Example: postgresql://user:pass@localhost:5432/mydb"
            )
        engine = create_engine(DB_URL, connect_args={"options": "-c default_transaction_read_only=on"}
                               if "postgres" in DB_TYPE else {})
        return engine.connect()

    raise RuntimeError(
        f"Unknown AEGIS_DB_TYPE='{DB_TYPE}'. Supported: sqlite | postgres | mysql"
    )


def introspect_schema() -> str:
    """
    Read actual DB schema from the connected database.
    Returns a formatted string: "Tables:\n- tablename(col1, col2, ...)\n..."
    Result is cached in module-level _SCHEMA_CACHE.
    Gracefully returns empty string on any error.
    """
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE:
        return _SCHEMA_CACHE

    try:
        if DB_TYPE == "sqlite":
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [row[0] for row in cursor.fetchall()]
                lines = ["Tables:"]
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [row[1] for row in cursor.fetchall()]
                    lines.append(f"- {table}({', '.join(cols)})")
                _SCHEMA_CACHE = "\n".join(lines)
            finally:
                conn.close()

        elif DB_TYPE in ("postgres", "postgresql", "mysql"):
            from sqlalchemy import create_engine, text as sa_text
            engine = create_engine(DB_URL)
            with engine.connect() as conn:
                if "mysql" in DB_TYPE:
                    result = conn.execute(sa_text(
                        "SELECT TABLE_NAME, COLUMN_NAME "
                        "FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() "
                        "ORDER BY TABLE_NAME, ORDINAL_POSITION"
                    ))
                else:
                    result = conn.execute(sa_text(
                        "SELECT table_name, column_name "
                        "FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "ORDER BY table_name, ordinal_position"
                    ))
                rows = result.fetchall()

            table_cols: dict = {}
            for table_name, col_name in rows:
                table_cols.setdefault(table_name, []).append(col_name)

            lines = ["Tables:"]
            for tname, cols in table_cols.items():
                lines.append(f"- {tname}({', '.join(cols)})")
            _SCHEMA_CACHE = "\n".join(lines)

    except Exception as e:
        logger.warning(f"introspect_schema failed: {e}")
        _SCHEMA_CACHE = ""

    return _SCHEMA_CACHE


async def run_db_pipeline(query: str, column_rules: dict, llm_service=None, user_id: str = "", user_role: str = "employee") -> dict:
    """
    Executes read-only database queries relevant to the user's query.
    Applies column-level access rules before returning.

    First attempts keyword-based SQL matching. If no rows are found and
    llm_service is provided, falls back to text-to-SQL via LLM.

    Returns governed rows ready for the firewall — NOT yet summarized.
    """
    query_lower = query.lower()
    conn = get_readonly_connection()
    results = {
        "rows": [],
        "sources": [],
        "columns_blocked": [],
        "columns_anonymized": []
    }

    try:
        cursor = conn.cursor()

        # Patient count / patient status queries
        if any(kw in query_lower for kw in ["patient", "patient count", "how many patient", "active patient", "patient status"]):
            cursor.execute("""
                SELECT patient_status, COUNT(*) as count
                FROM patients
                GROUP BY patient_status
                ORDER BY count DESC
                LIMIT 20
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "patients", column_rules)
            governed = apply_row_filter(governed, "patients", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("patients table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Medical conditions / diagnosis queries
        if any(kw in query_lower for kw in ["condition", "diagnosis", "diagnos", "medical condition", "icd", "disease"]):
            cursor.execute("""
                SELECT diagnosis, COUNT(*) as count
                FROM medical_records
                WHERE diagnosis IS NOT NULL AND diagnosis != ''
                GROUP BY diagnosis
                ORDER BY count DESC
                LIMIT 15
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "medical_records", column_rules)
            governed = apply_row_filter(governed, "medical_records", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("medical_records table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Headcount / department / employees queries
        if any(kw in query_lower for kw in ["headcount", "team size", "how many employee", "department size", "employee count", "staff count", "employees in"]):
            cursor.execute("""
                SELECT d.department_name, COUNT(e.employee_id) as employee_count, d.budget
                FROM departments d
                LEFT JOIN employees e ON e.department_id = d.department_id
                GROUP BY d.department_id, d.department_name, d.budget
                ORDER BY employee_count DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "departments", column_rules)
            governed = apply_row_filter(governed, "departments", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("departments table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Insurance / insurance_info queries
        if any(kw in query_lower for kw in ["insurance", "coverage", "insurer", "insurance record", "insurance information"]):
            cursor.execute("""
                SELECT
                    COUNT(*) as total_insurance_records,
                    COUNT(DISTINCT patient_id) as patients_with_insurance,
                    COUNT(DISTINCT insurance_provider) as distinct_providers
                FROM insurance_info
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "insurance_info", column_rules)
            governed = apply_row_filter(governed, "insurance_info", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("insurance_info table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Appointment queries
        if any(kw in query_lower for kw in ["appointment", "scheduled", "visit", "appointment status"]):
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM appointments
                GROUP BY status
                ORDER BY count DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "appointments", column_rules)
            governed = apply_row_filter(governed, "appointments", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("appointments table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Prescription queries
        if any(kw in query_lower for kw in ["prescription", "prescribed", "medication", "drug", "medicine"]):
            cursor.execute("""
                SELECT COUNT(*) as total_prescriptions
                FROM prescriptions
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "prescriptions", column_rules)
            governed = apply_row_filter(governed, "prescriptions", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("prescriptions table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Billing queries
        if any(kw in query_lower for kw in ["billing", "bill", "billed", "invoice", "charge", "payment", "paid"]):
            cursor.execute("""
                SELECT status, COUNT(*) as count, ROUND(SUM(total_amount),2) as total_amount
                FROM billing
                GROUP BY status
                ORDER BY count DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "billing", column_rules)
            governed = apply_row_filter(governed, "billing", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("billing table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Lab results queries
        if any(kw in query_lower for kw in ["lab", "lab result", "test result", "cbc", "hba1c", "lipid", "urinalysis", "blood test"]):
            cursor.execute("""
                SELECT test_name, COUNT(*) as count,
                       SUM(CASE WHEN abnormal_flag IN ('Abnormal', 'Critical') THEN 1 ELSE 0 END) as abnormal_count
                FROM lab_results
                GROUP BY test_name
                ORDER BY count DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "lab_results", column_rules)
            governed = apply_row_filter(governed, "lab_results", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("lab_results table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Payroll queries
        if any(kw in query_lower for kw in ["payroll", "salary", "pay", "wage", "compensation", "net pay", "gross pay"]):
            cursor.execute("""
                SELECT e.department_id, COUNT(p.payroll_id) as payroll_records,
                       ROUND(AVG(p.gross_salary),2) as avg_gross, ROUND(AVG(p.net_pay),2) as avg_net
                FROM payroll p
                JOIN employees e ON e.employee_id = p.employee_id
                GROUP BY e.department_id
                ORDER BY avg_gross DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "payroll", column_rules)
            governed = apply_row_filter(governed, "payroll", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("payroll table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Leave request queries
        if any(kw in query_lower for kw in ["leave request", "leave balance", "sick leave", "vacation", "pto", "time off", "fmla", "maternity"]):
            cursor.execute("""
                SELECT
                    leave_type,
                    status,
                    COUNT(*) as count,
                    SUM(COUNT(*)) OVER () as total_requests
                FROM leave_requests
                GROUP BY leave_type, status
                ORDER BY count DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "leave_requests", column_rules)
            governed = apply_row_filter(governed, "leave_requests", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("leave_requests table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Medical facilities queries
        if any(kw in query_lower for kw in ["facility", "facilities", "icu", "emergency", "ward", "bed", "capacity", "operating"]):
            cursor.execute("""
                SELECT facility_name, facility_type, capacity
                FROM medical_facilities
                ORDER BY capacity DESC
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "medical_facilities", column_rules)
            governed = apply_row_filter(governed, "medical_facilities", user_id, user_role, allow_rows_without_owner_key=True)
            results["rows"] += governed
            results["sources"].append("medical_facilities table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

    except sqlite3.Error as e:
        logger.error(f"DB Pipeline error: {e}")
    finally:
        conn.close()

    # If keyword matching found nothing and an LLM is available, try text-to-SQL
    if not results["rows"] and llm_service is not None:
        logger.info("Keyword DB pipeline found no rows — falling back to text-to-SQL")
        text_to_sql_results = await run_text_to_sql(query, column_rules, llm_service, user_id=user_id, user_role=user_role)
        if text_to_sql_results["rows"]:
            return text_to_sql_results

    return results


_FORBIDDEN_SQL_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "create", "truncate", "replace", "merge")

_TEXT_TO_SQL_SYSTEM = """You are an expert SQL assistant for a medical enterprise database.
Given a user question and a database schema, generate a safe, read-only SQL SELECT query that answers the question.

Rules:
1. Only generate SELECT statements.
2. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, or MERGE.
3. Always use LIMIT 100 unless the user asks for a count/aggregate.
4. Return ONLY the raw SQL — no explanations, no markdown fences, no extra text.
5. If the question cannot be answered with the schema, return: SELECT 'Unable to answer this question with available data' AS message;
6. Key tables with data: patients (5000 rows), appointments (2931 rows), insurance_info (4512 rows), medical_records (1463 rows), employees (405 rows), prescriptions (868 rows), departments (10 rows), billing, lab_results, leave_requests, payroll, medical_facilities.
"""


async def run_text_to_sql(query: str, column_rules: dict, llm_service, user_id: str = "", user_role: str = "employee") -> dict:
    """
    Text-to-SQL pipeline:
    1. Introspect the real DB schema (cached after first call).
    2. Ask the LLM to generate a SELECT SQL query from the user's natural language.
    3. Validate the SQL (no write operations).
    4. Execute against the database.
    5. Apply column-level RBAC.
    6. Return same format as run_db_pipeline.
    """
    results = {
        "rows": [],
        "sources": [],
        "columns_blocked": [],
        "columns_anonymized": [],
    }

    # 1. Get real schema (cached after first call)
    schema = introspect_schema()
    if not schema:
        logger.warning("run_text_to_sql: schema introspection returned empty — aborting")
        return results

    # 2. Generate SQL via LLM
    prompt = f"Schema:\n{schema}\n\nQuestion: {query}\n\nSQL:"
    try:
        generated_sql = await llm_service.chat(
            [
                {"role": "system", "content": _TEXT_TO_SQL_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=512,
        )
    except Exception as e:
        logger.error(f"Text-to-SQL LLM call failed: {e}")
        return results

    # Clean up LLM output
    sql = generated_sql.strip()
    # Strip any accidental markdown fences
    if sql.startswith("```"):
        sql = "\n".join(
            line for line in sql.splitlines()
            if not line.startswith("```")
        ).strip()

    logger.info(f"Text-to-SQL generated: {sql[:200]}")

    # 3. Validate — reject any write operations
    sql_lower = sql.lower()
    for forbidden in _FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{re.escape(forbidden)}\b", sql_lower):
            logger.warning(f"Text-to-SQL generated forbidden keyword '{forbidden}' — rejected")
            return results

    if not sql_lower.strip().startswith("select"):
        logger.warning("Text-to-SQL did not produce a SELECT statement — rejected")
        return results

    # 4. Execute
    conn = get_readonly_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        raw_rows = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Text-to-SQL execution error: {e} | SQL: {sql[:300]}")
        return results
    finally:
        conn.close()

    if not raw_rows:
        return results

    # 5. Apply column RBAC.
    # A generated query may touch multiple tables (JOINs). Governing by a single
    # inferred table lets a permissive reference table (e.g. departments: ALL ALLOW)
    # leak a sensitive column from a joined table (e.g. patient_pii.ssn). Govern by
    # the strictest rule across EVERY referenced table instead.
    referenced = _referenced_tables(sql_lower)
    primary_table = referenced[0] if referenced else _infer_table_name(sql_lower)
    governance_tables = referenced or ([primary_table] if primary_table else [])
    governed, blocked, anonymized = apply_column_rules_multi(raw_rows, governance_tables, column_rules)

    # Row-level filter: if the query touches a personal table, enforce ownership on it;
    # otherwise fall back to the primary table. STRICT mode (no pass for rows missing
    # the ownership column) — the SELECT list of LLM-generated SQL is attacker-shaped,
    # so a row that can't prove ownership must be dropped, not waved through.
    personal_refs = [t for t in referenced if t in PERSONAL_TABLES]
    row_filter_table = personal_refs[0] if personal_refs else (primary_table or "")
    governed = apply_row_filter(governed, row_filter_table, user_id, user_role)

    results["rows"] = governed
    results["sources"].append(f"HR database (text-to-SQL: {primary_table or 'query'})")
    results["columns_blocked"] = blocked
    results["columns_anonymized"] = anonymized

    return results


_KNOWN_TABLES = [
    "patients", "medical_records", "appointments", "prescriptions",
    "insurance_info", "billing", "lab_results", "payroll", "leave_requests",
    "medical_facilities", "departments", "employees", "employee_benefits",
    "employee_roles", "leave_balance", "leave_policies", "patient_pii",
    "patient_contacts", "performance_reviews", "training_records",
    "hipaa_access_logs", "incident_reports", "compliance_audits",
    "operational_metrics", "revenue_streams", "budget_allocation",
    "expense_reports", "contracts", "supply_chain", "inventory",
    "it_assets", "it_tickets", "system_uptime", "accounts_payable",
    "claims_processing", "regulatory_documents", "reporting_hierarchy",
    "teams", "certifications", "locations", "medical_specialties",
]


def _infer_table_name(sql_lower: str) -> str:
    """Heuristically extract the primary table name from a SQL query."""
    for tbl in _KNOWN_TABLES:
        if tbl in sql_lower:
            return tbl
    return ""


def _referenced_tables(sql_lower: str) -> list:
    """
    Return every known table referenced in a SQL query (word-boundary matched).

    Used to govern text-to-SQL results by the strictest rule across all tables a
    query touches, so a JOIN cannot smuggle a sensitive column past column rules.
    """
    return [t for t in _KNOWN_TABLES if re.search(rf"\b{re.escape(t)}\b", sql_lower)]
