"""
Regression tests for the security fixes from the product audit.

Covers:
  R-01  department authorization on retrieval targets
  R-02  answer-cache user isolation
  R-03  text-to-SQL JOIN column governance (confirmed SSN leak)

No live LLM / DB required — all assertions run against the internal governance code.
"""
import pytest

from aegis.rbac.rbac_module import (
    RBACModule,
    apply_column_rules_multi,
    load_column_rules,
)
from aegis.core.db_pipeline import _referenced_tables
from aegis.core.master_agent import MasterAgent


# ── R-01 department authorization ─────────────────────────────────────────────
@pytest.fixture
def rbac():
    return RBACModule()


def test_employee_denied_finance_department(rbac):
    allowed, denied = rbac.authorize_departments("employee", ["finance"])
    assert allowed == []
    assert "finance" in denied


def test_employee_allowed_hr_and_general(rbac):
    allowed, denied = rbac.authorize_departments("employee", ["hr", "general"])
    assert set(allowed) == {"hr", "general"}
    assert denied == []


def test_employee_mixed_request_trims_to_permitted(rbac):
    allowed, denied = rbac.authorize_departments("employee", ["hr", "engineering", "legal"])
    assert allowed == ["hr"]
    assert set(denied) == {"engineering", "legal"}


def test_general_is_always_readable(rbac):
    for role in ("employee", "manager"):
        allowed, _ = rbac.authorize_departments(role, ["general"])
        assert allowed == ["general"]


def test_admin_is_unrestricted(rbac):
    requested = ["finance", "legal", "sales", "engineering", "hr"]
    allowed, denied = rbac.authorize_departments("admin", requested)
    assert allowed == requested
    assert denied == []


# ── R-03 text-to-SQL JOIN governance ──────────────────────────────────────────
def test_referenced_tables_detects_all_joined_tables():
    sql = "select pii.ssn, d.department_name from patient_pii pii join departments d on 1=1"
    refs = _referenced_tables(sql.lower())
    assert "patient_pii" in refs
    assert "departments" in refs


def test_employee_join_blocks_ssn_from_permissive_join():
    """The confirmed leak: patient_pii JOIN departments must not surface a raw SSN."""
    emp_rules = load_column_rules("config/access_rules.yaml", "employee")
    sql = "select pii.ssn, d.department_name from patient_pii pii join departments d"
    tables = _referenced_tables(sql.lower())
    rows = [{"ssn": "123-45-6789", "department_name": "Cardiology"}]
    governed, blocked, _ = apply_column_rules_multi(rows, tables, emp_rules)
    assert "ssn" not in governed[0], "SSN leaked through a JOIN"
    assert "ssn" in blocked


def test_admin_multi_table_still_sees_all():
    admin_rules = load_column_rules("config/access_rules.yaml", "admin")
    tables = ["patient_pii", "departments"]
    rows = [{"ssn": "123-45-6789", "department_name": "Cardiology"}]
    governed, blocked, _ = apply_column_rules_multi(rows, tables, admin_rules)
    assert governed[0]["ssn"] == "123-45-6789"
    assert blocked == []


def test_strictest_rule_wins_across_tables():
    # net_pay is ANONYMIZE for manager on payroll; a joined ALL:ALLOW table must not
    # downgrade it to ALLOW.
    mgr_rules = load_column_rules("config/access_rules.yaml", "manager")
    rows = [{"net_pay": 60000, "department_name": "HR"}]
    governed, _, anonymized = apply_column_rules_multi(rows, ["payroll", "departments"], mgr_rules)
    assert "net_pay" in anonymized
    assert governed[0]["net_pay"] != 60000


# ── R-02 cache key user isolation ─────────────────────────────────────────────
def test_cache_key_differs_by_user():
    k_alice = MasterAgent._cache_key("what is my leave balance?", "hr", "employee", "alice")
    k_bob = MasterAgent._cache_key("what is my leave balance?", "hr", "employee", "bob")
    assert k_alice != k_bob


def test_cache_key_stable_for_same_user():
    k1 = MasterAgent._cache_key("q", "hr", "employee", "alice")
    k2 = MasterAgent._cache_key("q", "hr", "employee", "alice")
    assert k1 == k2


# ── R-04 row-level security: no bypass by omitting the ownership column ──────
from aegis.rbac.rbac_module import apply_row_filter, _normalize_rule, apply_column_rules


def test_text_to_sql_rows_without_owner_key_are_dropped_for_manager():
    """The confirmed leak: SELECT first_name, salary FROM employees (no
    employee_id in the output) must return zero rows to a manager."""
    rows = [
        {"first_name": "Alice", "salary": 95000},
        {"first_name": "Bob", "salary": 60000},
    ]
    filtered = apply_row_filter(rows, "employees", user_id="mgr1", user_role="manager")
    assert filtered == []


def test_text_to_sql_rows_without_owner_key_are_dropped_for_employee():
    rows = [{"first_name": "Alice", "salary": 95000}]
    filtered = apply_row_filter(rows, "payroll", user_id="EMP0042", user_role="employee")
    assert filtered == []


def test_employee_sees_only_own_rows_when_owner_key_present():
    rows = [
        {"employee_id": "EMP0042", "leave_type": "sick"},
        {"employee_id": "EMP0099", "leave_type": "vacation"},
    ]
    filtered = apply_row_filter(rows, "leave_requests", user_id="EMP0042", user_role="employee")
    assert filtered == [{"employee_id": "EMP0042", "leave_type": "sick"}]


def test_manager_sees_own_and_reports_rows():
    rows = [
        {"employee_id": "EMP0001", "manager_id": "MGR9", "status": "approved"},
        {"employee_id": "EMP0002", "manager_id": "MGR7", "status": "pending"},
    ]
    filtered = apply_row_filter(rows, "leave_requests", user_id="MGR9", user_role="manager")
    assert len(filtered) == 1 and filtered[0]["manager_id"] == "MGR9"


def test_trusted_aggregate_rows_pass_for_canned_pipeline():
    """Developer-written aggregate SQL (fixed SELECT list) may return
    ownerless aggregate rows — that flag must never be set for text-to-SQL."""
    rows = [{"leave_type": "sick", "count": 12}]
    filtered = apply_row_filter(
        rows, "leave_requests", user_id="EMP0042", user_role="employee",
        allow_rows_without_owner_key=True,
    )
    assert filtered == rows


def test_admin_row_filter_unrestricted():
    rows = [{"first_name": "Alice", "salary": 95000}]
    assert apply_row_filter(rows, "employees", "root", "admin") == rows


# ── R-05 unrecognized column rules fail closed ────────────────────────────────

def test_unknown_rule_value_fails_closed():
    assert _normalize_rule("Block") == "BLOCK"      # typo'd case
    assert _normalize_rule("DENY") == "BLOCK"       # wrong vocabulary
    assert _normalize_rule(None) == "BLOCK"
    assert _normalize_rule("ALLOW") == "ALLOW"
    assert _normalize_rule("ANONYMIZE") == "ANONYMIZE"


def test_typoed_rule_blocks_column_instead_of_allowing():
    rules = {"employees": {"salary": "Block", "name": "ALLOW"}}  # note the typo
    rows = [{"salary": 95000, "name": "Alice"}]
    governed, blocked, _ = apply_column_rules(rows, "employees", rules)
    assert "salary" not in governed[0], "typo'd rule must fail closed, not open"
    assert "salary" in blocked
    assert governed[0]["name"] == "Alice"


# ── R-06 project_id sanitization (path traversal / pickle write) ─────────────
from aegis.security import InvalidProjectId, sanitize_project_id


def test_path_traversal_project_ids_rejected():
    for evil in ("../evil", "..", "a/b", "a\\b", "hr; rm -rf", "../../tmp/x", "HR "):
        with pytest.raises(InvalidProjectId):
            sanitize_project_id(evil)


def test_valid_project_ids_pass():
    for ok in ("hr", "general", "customer_success", "_session_bob_ab12cd34ef56", "proj_2024"):
        assert sanitize_project_id(ok) == ok


def test_blank_project_id_uses_default():
    assert sanitize_project_id("  ", default="general") == "general"
    with pytest.raises(InvalidProjectId):
        sanitize_project_id("")


# ── R-07 conversation history is user-scoped ──────────────────────────────────
from aegis.core.conversation_store import ConversationStore


def test_conversation_history_is_isolated_between_users():
    store = ConversationStore()
    store.append("alice", "conv-1", "user", "my salary question")
    store.append("alice", "conv-1", "assistant", "answer for alice")

    # Bob presents the same conversation_id — must see nothing of Alice's.
    assert store.get_history("bob", "conv-1") == []
    assert len(store.get_history("alice", "conv-1")) == 2

    # Bob writing to the same id must not poison Alice's history.
    store.append("bob", "conv-1", "user", "injected")
    assert all(m["content"] != "injected" for m in store.get_history("alice", "conv-1"))


# ── R-08 users env parsing with employee_id mapping ───────────────────────────

def test_aegis_users_parses_optional_employee_id(monkeypatch):
    from api import auth as auth_mod
    monkeypatch.setenv(
        "AEGIS_USERS",
        "alice:manager:pw1:EMP0001,bob:employee:pw2,broken:entry",
    )
    monkeypatch.setenv("AEGIS_PASSWORD", "")
    users = auth_mod._load_users()
    assert users["alice"]["employee_id"] == "EMP0001"
    assert users["bob"]["employee_id"] == ""
    assert "broken" not in users


def test_jwt_roundtrip_carries_employee_id():
    import jwt as pyjwt
    from api import auth as auth_mod
    token = auth_mod._create_access_token(
        {"sub": "alice", "role": "manager", "emp": "EMP0001"}
    )
    payload = pyjwt.decode(token, auth_mod.SECRET_KEY, algorithms=[auth_mod.ALGORITHM])
    assert payload["sub"] == "alice"
    assert payload["emp"] == "EMP0001"
