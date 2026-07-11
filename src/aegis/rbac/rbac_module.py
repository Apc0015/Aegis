import logging
from aegis.config import RBAC_ROLES
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Tables that contain personal/employee-specific records
PERSONAL_TABLES = {
    "employees",
    "leave_requests",
    "employee_benefits",
    "performance_reviews",
    "training_records",
    "payroll",
    "patient_pii",
    "medical_records",
    "hipaa_access_logs",
}

# Tables that are reference/public data — all roles can see all rows
REFERENCE_TABLES = {
    "departments",
    "medical_specialties",
    "locations",
    "leave_policies",
    "leave_balance",
    "regulatory_documents",
    "medical_facilities",
    "operational_metrics",
}

@dataclass
class AccessDecision:
    permitted: bool
    user_role: str
    user_id: str
    query: str
    permitted_departments: List[str]
    denial_reason: Optional[str] = None

class RBACModule:
    """
    Enforces role-based access control at the retrieval layer.
    Called BEFORE any retrieval begins — not at the response layer.
    """

    def __init__(self):
        self.roles = RBAC_ROLES

    def check_access(
        self,
        user_id: str,
        user_role: str,
        query: str,
        target_departments: Optional[List[str]] = None,
    ) -> AccessDecision:
        """
        Returns AccessDecision. If not permitted, retrieval must not proceed.
        """
        role_config = self.roles.get(user_role)
        if not role_config:
            return AccessDecision(
                permitted=False,
                user_role=user_role,
                user_id=user_id,
                query=query,
                permitted_departments=[],
                denial_reason=f"Unknown role: {user_role}",
            )

        permitted_depts = role_config["departments"]

        # If specific departments are requested, check intersection
        if target_departments:
            allowed = [d for d in target_departments if d in permitted_depts]
            if not allowed:
                return AccessDecision(
                    permitted=False,
                    user_role=user_role,
                    user_id=user_id,
                    query=query,
                    permitted_departments=[],
                    denial_reason=(
                        f"Your role ({role_config['label']}) does not have access "
                        f"to the requested department(s): {', '.join(target_departments)}."
                    ),
                )
            return AccessDecision(
                permitted=True,
                user_role=user_role,
                user_id=user_id,
                query=query,
                permitted_departments=allowed,
            )

        return AccessDecision(
            permitted=True,
            user_role=user_role,
            user_id=user_id,
            query=query,
            permitted_departments=permitted_depts,
        )

    def get_permitted_departments(self, user_role: str) -> List[str]:
        role_config = self.roles.get(user_role, {})
        return role_config.get("departments", [])

    def can_delete_docs(self, user_role: str) -> bool:
        return self.roles.get(user_role, {}).get("can_delete_docs", False)

    def can_export_audit(self, user_role: str) -> bool:
        return self.roles.get(user_role, {}).get("can_export_audit", False)

    def authorize_departments(
        self,
        user_role: str,
        requested_departments: List[str],
    ) -> tuple:
        """
        Restrict a set of requested retrieval departments to those the role may access.

        This is the enforcement point the retrieval pipeline was missing: department
        routing decides *where to look*, and this decides *where the role is allowed
        to look*. Returns (allowed, denied).

        Admin is unrestricted — the RBAC department allow-list is intentionally not
        exhaustive of every routable department, so admins bypass the filter entirely.
        Every non-admin role is limited to its configured departments (plus 'general',
        which is always readable).
        """
        if user_role == "admin":
            return list(requested_departments), []

        permitted = set(self.get_permitted_departments(user_role)) | {"general"}
        allowed = [d for d in requested_departments if d in permitted]
        denied = [d for d in requested_departments if d not in permitted]
        return allowed, denied



def apply_row_filter(
    rows: list,
    table_name: str,
    user_id: str,
    user_role: str,
    allow_rows_without_owner_key: bool = False,
) -> list:
    """
    Apply row-level security filters.

    Employees see only their own records in personal tables. Managers see their
    own or their reports' records. Admins see all.

    SECURITY — fail closed by default. A personal-table row is returned to a
    non-admin ONLY when it carries an ownership column (``employee_id`` /
    ``manager_id``) matching the caller. Previously rows *lacking* the column were
    passed through ("reference-like"), which let text-to-SQL dump every row simply
    by not selecting the ownership column (e.g. ``SELECT first_name, salary FROM
    employees``). Missing ownership column now means "not provably yours" → dropped.

    allow_rows_without_owner_key: set ONLY for developer-written aggregate SQL
      (the canned keyword pipeline), where the SELECT list is fixed in code and
      known to contain no per-person data. Never set it for LLM-generated SQL —
      there the SELECT list is attacker-influenced.
    """
    original_count = len(rows)

    # Admins have unrestricted access to all rows
    if user_role == "admin":
        logger.debug(
            "apply_row_filter: admin user=%s, table=%s — all %d rows passed through",
            user_id, table_name, original_count,
        )
        return rows

    def _owned_by_caller(row: dict, include_manager: bool) -> bool:
        if "employee_id" not in row and "manager_id" not in row:
            return allow_rows_without_owner_key
        if row.get("employee_id") == user_id:
            return True
        return include_manager and row.get("manager_id") == user_id

    if user_role == "manager":
        if table_name in PERSONAL_TABLES:
            filtered = [row for row in rows if _owned_by_caller(row, include_manager=True)]
        else:
            # Reference tables and non-personal aggregates — managers may see.
            filtered = rows

        removed = original_count - len(filtered)
        logger.debug(
            "apply_row_filter: manager user=%s, table=%s — %d/%d rows returned (%d filtered)",
            user_id, table_name, len(filtered), original_count, removed,
        )
        return filtered

    if user_role == "employee":
        if table_name in PERSONAL_TABLES:
            filtered = [row for row in rows if _owned_by_caller(row, include_manager=False)]
        elif table_name in REFERENCE_TABLES:
            # Reference/policy data — employees can see all rows
            filtered = rows
        else:
            # Unknown table — deny by returning empty (principle of least privilege)
            filtered = []

        removed = original_count - len(filtered)
        logger.debug(
            "apply_row_filter: employee user=%s, table=%s — %d/%d rows returned (%d filtered)",
            user_id, table_name, len(filtered), original_count, removed,
        )
        return filtered

    # Unknown role — safest to return nothing
    logger.debug(
        "apply_row_filter: unknown role=%s user=%s, table=%s — 0 rows returned",
        user_role, user_id, table_name,
    )
    return []


def load_column_rules(access_rules_path: str, user_role: str) -> dict:
    """
    Load per-role column rules from access_rules.yaml.
    Returns dict like: {"employees": {"salary": "BLOCK", "name": "ALLOW", ...}}
    """
    import yaml
    with open(access_rules_path, 'r') as f:
        rules = yaml.safe_load(f)
    role_rules = rules.get("roles", {}).get(user_role, {})
    return role_rules.get("db_column_rules", {})


VALID_RULES = ("ALLOW", "ANONYMIZE", "BLOCK")


def _normalize_rule(rule) -> str:
    """
    Coerce a rule value to one of VALID_RULES, failing closed.

    Anything that is not exactly ALLOW / ANONYMIZE / BLOCK (a typo like "Block",
    "DENY", None, a stray int) is treated as BLOCK. Security rules must never
    grant access by accident — an unrecognized rule is the safest kind to deny.
    """
    return rule if rule in VALID_RULES else "BLOCK"


def apply_column_rules(rows: list, table: str, column_rules: dict) -> tuple:
    """
    Apply ALLOW / ANONYMIZE / BLOCK rules to database rows.
    Returns: (governed_rows, blocked_columns, anonymized_columns)

    Unrecognized rule values fail closed (treated as BLOCK) — see _normalize_rule.
    """
    blocked = []
    anonymized = []
    governed_rows = []

    # Admin-style roles can define ALL_TABLES: ALL: ALLOW.
    all_tables_rules = column_rules.get("ALL_TABLES", {})
    table_rules = column_rules.get(table, all_tables_rules)

    for row in rows:
        governed_row = {}
        for col, val in row.items():
            rule = _normalize_rule(table_rules.get(col, table_rules.get("ALL", "BLOCK")))
            if rule == "ALLOW":
                governed_row[col] = val
            elif rule == "ANONYMIZE":
                if col not in anonymized:
                    anonymized.append(col)
                governed_row[col] = _anonymize_value(col, val)
            else:  # BLOCK (or anything unrecognized → fail closed)
                if col not in blocked:
                    blocked.append(col)
                # Column is excluded entirely — not passed forward
        governed_rows.append(governed_row)

    return governed_rows, blocked, anonymized


# Rule strictness ordering — used when a column could be governed by more than one
# table (e.g. a text-to-SQL JOIN). The strictest rule always wins.
_RULE_STRICTNESS = {"ALLOW": 0, "ANONYMIZE": 1, "BLOCK": 2}


def _resolve_rule_across_tables(column: str, tables: list, column_rules: dict) -> str:
    """
    Resolve the effective rule for *column* across every table referenced by a query.

    For each referenced table we look up the column's rule (falling back to that
    table's ``ALL`` default, or ``BLOCK`` when a role has no rules for the table),
    then keep the strictest rule found. This closes the JOIN governance gap where a
    single inferred table could grant ALLOW to a column that another referenced,
    sensitive table would BLOCK.
    """
    all_tables_rules = column_rules.get("ALL_TABLES", {})
    strictest = "ALLOW"
    seen = False
    for table in tables or [""]:
        table_rules = column_rules.get(table, all_tables_rules)
        rule = _normalize_rule(table_rules.get(column, table_rules.get("ALL", "BLOCK")))
        if not seen or _RULE_STRICTNESS.get(rule, 2) > _RULE_STRICTNESS.get(strictest, 2):
            strictest = rule
            seen = True
    return strictest


def apply_column_rules_multi(rows: list, tables: list, column_rules: dict) -> tuple:
    """
    Column governance for results that may span multiple tables (text-to-SQL JOINs).

    Same contract as apply_column_rules, but each column is governed by the strictest
    rule across ALL referenced tables rather than a single (possibly wrong) inferred
    table. Returns (governed_rows, blocked_columns, anonymized_columns).
    """
    blocked: list = []
    anonymized: list = []
    governed_rows: list = []

    for row in rows:
        governed_row = {}
        for col, val in row.items():
            rule = _resolve_rule_across_tables(col, tables, column_rules)
            if rule == "ALLOW":
                governed_row[col] = val
            elif rule == "ANONYMIZE":
                if col not in anonymized:
                    anonymized.append(col)
                governed_row[col] = _anonymize_value(col, val)
            else:  # BLOCK (or anything unrecognized → fail closed)
                if col not in blocked:
                    blocked.append(col)
        governed_rows.append(governed_row)

    return governed_rows, blocked, anonymized


def _anonymize_value(column: str, value) -> str:
    """Replace sensitive values with safe anonymized descriptions."""
    anonymize_map = {
        "salary": lambda v: (
            "lower salary range" if v and float(v) < 50000 else
            "mid salary range" if v and float(v) < 80000 else
            "upper salary range" if v else "not available"
        ),
        "salary_grade": lambda v: (
            "junior level" if v in ["junior", "associate"] else
            "mid level" if v in ["mid", "intermediate"] else
            "senior level" if v in ["senior", "lead", "principal"] else
            str(v) if v else "not available"
        ),
    }
    anonymizer = anonymize_map.get(column)
    return anonymizer(value) if anonymizer else "[anonymized]"
