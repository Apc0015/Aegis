from rapid.config import RBAC_ROLES
from dataclasses import dataclass
from typing import List, Optional

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


# ── Column-Level Access Rules ─────────────────────────────────────────────────

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


def apply_column_rules(rows: list, table: str, column_rules: dict) -> tuple:
    """
    Apply ALLOW / ANONYMIZE / BLOCK rules to database rows.
    Returns: (governed_rows, blocked_columns, anonymized_columns)
    """
    blocked = []
    anonymized = []
    governed_rows = []

    # hr_admin has ALL_TABLES: ALL: ALLOW — handle that first
    all_tables_rules = column_rules.get("ALL_TABLES", {})
    table_rules = column_rules.get(table, all_tables_rules)

    for row in rows:
        governed_row = {}
        for col, val in row.items():
            rule = table_rules.get(col, table_rules.get("ALL", "BLOCK"))
            if rule == "BLOCK":
                if col not in blocked:
                    blocked.append(col)
                # Column is excluded entirely — not passed forward
            elif rule == "ANONYMIZE":
                if col not in anonymized:
                    anonymized.append(col)
                governed_row[col] = _anonymize_value(col, val)
            else:  # ALLOW
                governed_row[col] = val
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
