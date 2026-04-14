"""
DB Pipeline — HR Database Query Pipeline
Read-only queries against the HR SQLite database.
Access rules applied column-by-column before firewall.
Returns governed rows — NOT yet through firewall.
Firewall is applied by the calling agent (master_agent.py).
"""
import sqlite3
import logging
from rapid.database.hr_database import get_readonly_connection
from rapid.rbac.rbac_module import apply_column_rules

logger = logging.getLogger(__name__)


async def run_db_pipeline(query: str, column_rules: dict) -> dict:
    """
    Executes read-only database queries relevant to the user's query.
    Applies column-level access rules before returning.

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

        # Leave / parental / annual / sick queries
        if any(kw in query_lower for kw in ["leave", "parental", "sick", "annual", "vacation", "time off", "pto"]):
            cursor.execute("""
                SELECT policy_name, category, effective_date, summary
                FROM policies
                WHERE category = 'leave'
                ORDER BY effective_date DESC
                LIMIT 5
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "policies", column_rules)
            results["rows"] += governed
            results["sources"].append("policies table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Benefits / insurance / 401k / health queries
        if any(kw in query_lower for kw in ["benefit", "insurance", "401k", "health", "dental", "vision", "enrollment"]):
            cursor.execute("""
                SELECT benefit_name, description, eligibility, enrollment_open, enrollment_close, provider
                FROM benefits
                ORDER BY benefit_name
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "benefits", column_rules)
            results["rows"] += governed
            results["sources"].append("benefits table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Headcount / team size / how many employees queries
        if any(kw in query_lower for kw in ["headcount", "team size", "how many", "employees in", "department size"]):
            cursor.execute("""
                SELECT department, total_headcount, full_time, part_time, contractors
                FROM headcount_summary
                WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM headcount_summary)
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "headcount_summary", column_rules)
            results["rows"] += governed
            results["sources"].append("headcount_summary table")
            results["columns_blocked"] += [c for c in blocked if c not in results["columns_blocked"]]
            results["columns_anonymized"] += [c for c in anonymized if c not in results["columns_anonymized"]]

        # Remote work / work from home / policy queries
        if any(kw in query_lower for kw in ["remote", "work from home", "wfh", "policy", "conduct", "guidelines"]):
            cursor.execute("""
                SELECT policy_name, category, effective_date, summary
                FROM policies
                WHERE category IN ('conduct', 'onboarding')
                ORDER BY effective_date DESC
                LIMIT 5
            """)
            raw_rows = [dict(row) for row in cursor.fetchall()]
            governed, blocked, anonymized = apply_column_rules(raw_rows, "policies", column_rules)
            results["rows"] += governed
            if "policies table" not in results["sources"]:
                results["sources"].append("policies table")

    except sqlite3.Error as e:
        logger.error(f"DB Pipeline error: {e}")
    finally:
        conn.close()

    return results


_HR_SCHEMA = """
Tables:
- employees(employee_id, full_name, department, job_title, employment_type, start_date, manager_id, salary, salary_grade, location, ssn, personal_email, status)
- leave_requests(request_id, employee_id, leave_type, start_date, end_date, days_requested, status, approved_by, submitted_at, notes)
- benefits(benefit_id, benefit_name, description, eligibility, enrollment_open, enrollment_close, provider, contact_info)
- employee_benefits(employee_id, benefit_id, enrollment_date, status)
- policies(policy_id, policy_name, category, effective_date, content, summary)
- performance_reviews(review_id, employee_id, reviewer_id, review_period, rating, notes, submitted_at)
- training_records(record_id, employee_id, training_name, completion_date, status, score)
- organizational_chart(node_id, employee_id, parent_employee_id, level, reporting_chain)
"""

_FORBIDDEN_SQL_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "create", "truncate", "replace", "merge")

_TEXT_TO_SQL_SYSTEM = """You are an expert SQL assistant for a HR database.
Given a user question and a database schema, generate a safe, read-only SQL SELECT query that answers the question.

Rules:
1. Only generate SELECT statements.
2. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, or MERGE.
3. Always use LIMIT 100 unless the user asks for a count/aggregate.
4. Return ONLY the raw SQL — no explanations, no markdown fences, no extra text.
5. If the question cannot be answered with the schema, return: SELECT 'Unable to answer this question with available data' AS message;
"""


async def run_text_to_sql(query: str, column_rules: dict, llm_service) -> dict:
    """
    Text-to-SQL pipeline:
    1. Ask the LLM to generate a SELECT SQL query from the user's natural language.
    2. Validate the SQL (no write operations).
    3. Execute against SQLite.
    4. Apply column-level RBAC.
    5. Return same format as run_db_pipeline.
    """
    results = {
        "rows": [],
        "sources": [],
        "columns_blocked": [],
        "columns_anonymized": [],
    }

    # 1. Generate SQL via LLM
    prompt = f"Schema:\n{_HR_SCHEMA}\n\nQuestion: {query}\n\nSQL:"
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

    # 2. Validate — reject any write operations
    sql_lower = sql.lower()
    for forbidden in _FORBIDDEN_SQL_KEYWORDS:
        if forbidden in sql_lower:
            logger.warning(f"Text-to-SQL generated forbidden keyword '{forbidden}' — rejected")
            return results

    if not sql_lower.strip().startswith("select"):
        logger.warning("Text-to-SQL did not produce a SELECT statement — rejected")
        return results

    # 3. Execute
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

    # 4. Apply column RBAC — infer table name from SQL heuristic
    table_name = _infer_table_name(sql_lower)
    governed, blocked, anonymized = apply_column_rules(raw_rows, table_name, column_rules)

    results["rows"] = governed
    results["sources"].append(f"HR database (text-to-SQL: {table_name or 'query'})")
    results["columns_blocked"] = blocked
    results["columns_anonymized"] = anonymized

    return results


def _infer_table_name(sql_lower: str) -> str:
    """Heuristically extract the primary table name from a SQL query."""
    known_tables = [
        "employees", "leave_requests", "benefits", "employee_benefits",
        "policies", "performance_reviews", "training_records", "organizational_chart",
    ]
    for tbl in known_tables:
        if tbl in sql_lower:
            return tbl
    return ""


def detect_db_intent(query: str) -> bool:
    """
    Quick heuristic: does this query need the HR database?
    Returns True if database records would help answer this query.
    """
    db_keywords = [
        "leave", "parental", "sick", "annual", "vacation", "pto", "time off",
        "benefit", "insurance", "401k", "health", "dental", "enrollment",
        "headcount", "team size", "how many employees", "department size",
        "salary", "compensation", "pay", "remote", "work from home",
        "my status", "my leave", "my benefits", "my record"
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in db_keywords)
