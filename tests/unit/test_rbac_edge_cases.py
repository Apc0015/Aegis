"""
RBAC edge-case suite — the fail-closed contract.

The governance core is proven; this suite pins down the *edges* a real customer
deployment will hit but a happy-path demo never does:

  * unrecognized roles                         → deny everywhere
  * malformed / typo'd / wrong-type rules      → treat as BLOCK
  * a column allowed in one JOINed table but
    absent from another table's rules          → strictest (BLOCK) wins
  * missing role in access_rules.yaml          → block every column
  * LLM-generated SQL that isn't a lone SELECT → reject before it executes

Every assertion here is "the system must NOT leak" — a regression that flips any
of these open is a security incident, which is why this file is a CI gate.
No live LLM or DB is required.
"""
import pytest

from aegis.rbac.rbac_module import (
    RBACModule,
    apply_column_rules,
    apply_column_rules_multi,
    apply_row_filter,
    load_column_rules,
    _normalize_rule,
    _resolve_rule_across_tables,
)

ACCESS_RULES_PATH = "config/access_rules.yaml"

# Roles that must never be recognized — any string not in RBAC_ROLES.
UNKNOWN_ROLES = ["", "guest", "contractor", "root", "ADMIN", "Employee", "superuser", "none"]


@pytest.fixture
def rbac():
    return RBACModule()


# ── Unrecognized role → deny at EVERY enforcement point ───────────────────────

@pytest.mark.parametrize("role", UNKNOWN_ROLES)
def test_check_access_denies_unknown_role(rbac, role):
    decision = rbac.check_access(
        user_id="u1", user_role=role, query="show me everything",
        target_departments=["hr"],
    )
    assert not decision.permitted
    assert decision.denial_reason


@pytest.mark.parametrize("role", UNKNOWN_ROLES)
def test_authorize_departments_denies_unknown_role(rbac, role):
    # Even 'general' (public content) must be denied to an unrecognized role.
    allowed, denied = rbac.authorize_departments(role, ["general", "hr", "finance"])
    assert allowed == [], f"unknown role {role!r} leaked department access"
    assert set(denied) == {"general", "hr", "finance"}


@pytest.mark.parametrize("role", UNKNOWN_ROLES)
def test_row_filter_drops_all_rows_for_unknown_role(rbac, role):
    rows = [
        {"employee_id": "EMP1", "salary": 100000},
        {"employee_id": "EMP2", "salary": 90000},
    ]
    # personal table AND reference table — both must yield nothing.
    assert apply_row_filter(rows, "employees", "EMP1", role) == []
    assert apply_row_filter(rows, "departments", "EMP1", role) == []


@pytest.mark.parametrize("role", UNKNOWN_ROLES)
def test_capabilities_default_false_for_unknown_role(rbac, role):
    assert rbac.can_delete_docs(role) is False
    assert rbac.can_export_audit(role) is False
    assert rbac.get_permitted_departments(role) == []


def test_unknown_role_column_rules_block_everything():
    """A role with no entry in access_rules.yaml gets an empty rule set, which
    must block every column rather than pass rows through unfiltered."""
    rules = load_column_rules(ACCESS_RULES_PATH, "does_not_exist")
    assert rules == {}
    rows = [{"ssn": "123-45-6789", "name": "Alice", "salary": 95000}]
    governed, blocked, _ = apply_column_rules(rows, "employees", rules)
    assert governed[0] == {}, "empty rule set must expose no columns"
    assert set(blocked) == {"ssn", "name", "salary"}


# ── Malformed / wrong-type rules → BLOCK ──────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "Block", "block", "DENY", "deny", "Allow", " ALLOW", "ALLOW ", "ANON",
    None, 0, 1, [], {}, ["ALLOW"], "TRUE", "yes", "*",
])
def test_normalize_rule_fails_closed(bad):
    assert _normalize_rule(bad) == "BLOCK"


@pytest.mark.parametrize("good", ["ALLOW", "ANONYMIZE", "BLOCK"])
def test_normalize_rule_passes_exact_valid_values(good):
    assert _normalize_rule(good) == good


def test_malformed_rule_value_blocks_column_single_table():
    rules = {"employees": {"salary": None, "bonus": 42, "name": "ALLOW", "ssn": "Block"}}
    rows = [{"salary": 95000, "bonus": 5000, "name": "Alice", "ssn": "123-45-6789"}]
    governed, blocked, _ = apply_column_rules(rows, "employees", rules)
    assert governed[0] == {"name": "Alice"}
    assert set(blocked) == {"salary", "bonus", "ssn"}


def test_malformed_rule_value_blocks_column_multi_table():
    rules = {"employees": {"salary": {"nested": "oops"}, "name": "ALLOW"}}
    rows = [{"salary": 95000, "name": "Alice"}]
    governed, blocked, _ = apply_column_rules_multi(rows, ["employees"], rules)
    assert "salary" not in governed[0]
    assert governed[0]["name"] == "Alice"
    assert "salary" in blocked


# ── JOIN: column in one table's rules but absent from another ──────────────────

def test_column_allowed_in_one_table_blocked_when_joined_with_unlisted_table():
    """A column that is ALLOW in one JOINed table but absent from another (which
    has no ALL default) is BLOCKED — the co-referenced table defaults it to BLOCK
    and strictest wins. Here `secret` is only in table_a's rules and `other` only
    in table_b's, so a JOIN of the two exposes neither. Fail-closed by design."""
    rules = {"table_a": {"secret": "ALLOW"}, "table_b": {"other": "ALLOW"}}
    rows = [{"secret": "topsecret", "other": "fine"}]
    governed, blocked, _ = apply_column_rules_multi(rows, ["table_a", "table_b"], rules)
    assert governed[0] == {}, "a column allowed in only one JOINed table must not leak"
    assert set(blocked) == {"secret", "other"}

    # And with only its own table referenced, each column is exposed normally.
    g_a, _, _ = apply_column_rules_multi([{"secret": "topsecret"}], ["table_a"], rules)
    assert g_a[0]["secret"] == "topsecret"


def test_join_strictness_allow_vs_anonymize_yields_anonymize():
    rules = {"table_a": {"col": "ALLOW"}, "table_b": {"col": "ANONYMIZE"}}
    assert _resolve_rule_across_tables("col", ["table_a", "table_b"], rules) == "ANONYMIZE"


def test_join_strictness_anonymize_vs_block_yields_block():
    rules = {"table_a": {"col": "ANONYMIZE"}, "table_b": {"col": "BLOCK"}}
    assert _resolve_rule_across_tables("col", ["table_a", "table_b"], rules) == "BLOCK"


def test_join_order_does_not_change_outcome():
    rules = {"table_a": {"col": "ALLOW"}, "table_b": {"col": "BLOCK"}}
    forward = _resolve_rule_across_tables("col", ["table_a", "table_b"], rules)
    reverse = _resolve_rule_across_tables("col", ["table_b", "table_a"], rules)
    assert forward == reverse == "BLOCK"


def test_empty_table_list_fails_closed():
    """No resolvable table context → BLOCK, never ALLOW."""
    rules = {"employees": {"salary": "ALLOW"}}
    assert _resolve_rule_across_tables("salary", [], rules) == "BLOCK"


def test_admin_all_tables_allows_across_unlisted_join():
    admin_rules = load_column_rules(ACCESS_RULES_PATH, "admin")
    rows = [{"ssn": "123-45-6789", "diagnosis": "confidential", "dept": "Cardiology"}]
    governed, blocked, _ = apply_column_rules_multi(
        rows, ["patient_pii", "medical_records", "some_new_table"], admin_rules
    )
    assert governed[0]["ssn"] == "123-45-6789"
    assert blocked == []


# ── Real-config property test: PII never leaks to non-admins ───────────────────

@pytest.mark.parametrize("role", ["employee", "manager"])
def test_patient_pii_never_leaks_to_non_admin_from_real_config(role):
    rules = load_column_rules(ACCESS_RULES_PATH, role)
    rows = [{"ssn": "123-45-6789", "first_name": "Jane", "date_of_birth": "1980-01-01"}]
    governed, blocked, _ = apply_column_rules(rows, "patient_pii", rules)
    assert governed[0] == {}, f"{role} saw patient_pii columns"
    assert set(blocked) == {"ssn", "first_name", "date_of_birth"}


def test_hipaa_logs_blocked_for_non_admins_from_real_config():
    for role in ("employee", "manager"):
        rules = load_column_rules(ACCESS_RULES_PATH, role)
        rows = [{"access_id": 1, "user_id": "u", "patient_id": "p", "accessed_at": "now"}]
        governed, _, _ = apply_column_rules(rows, "hipaa_access_logs", rules)
        assert governed[0] == {}, f"{role} saw hipaa_access_logs"


# ── Read-only SQL validator (text-to-SQL defence-in-depth) ────────────────────

from aegis.core.db_pipeline import _is_safe_readonly_select


@pytest.mark.parametrize("sql", [
    "SELECT * FROM departments",
    "select name from departments where id = 1",
    "SELECT count(*) FROM employees;",           # single trailing semicolon ok
    "  select 1  ",
])
def test_safe_select_accepted(sql):
    ok, _ = _is_safe_readonly_select(sql)
    assert ok, f"legitimate SELECT rejected: {sql!r}"


@pytest.mark.parametrize("sql", [
    "SELECT 1; SELECT * FROM patient_pii",       # stacked SELECTs
    "SELECT 1; DROP TABLE patient_pii",          # stacked write
    "UPDATE employees SET salary = 0",
    "DELETE FROM payroll",
    "DROP TABLE patient_pii",
    "INSERT INTO employees VALUES (1)",
    "TRUNCATE employees",
    "ALTER TABLE employees ADD COLUMN x INT",
    "REPLACE INTO employees VALUES (1)",
    "WITH x AS (SELECT 1) SELECT * FROM x",      # CTE lead — fail closed (not SELECT-led)
    "",
    "   ",
    ";",
])
def test_unsafe_sql_rejected(sql):
    ok, reason = _is_safe_readonly_select(sql)
    assert not ok, f"unsafe SQL accepted: {sql!r}"
    assert reason
