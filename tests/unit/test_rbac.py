"""
Unit tests for RBAC module — no live LLM required.
"""
import pytest

from aegis.rbac.rbac_module import (
    RBACModule,
    apply_column_rules,
)


@pytest.fixture
def rbac():
    return RBACModule()


# ── Department access tests ───────────────────────────────────────────────────

def test_employee_blocked_from_finance_dept(rbac):
    decision = rbac.check_access(
        user_id="emp1",
        user_role="employee",
        query="what is our Q3 revenue?",
        target_departments=["finance"],
    )
    assert not decision.permitted
    assert decision.denial_reason is not None


def test_manager_permitted_hr_dept(rbac):
    decision = rbac.check_access(
        user_id="mgr1",
        user_role="manager",
        query="how many days of leave do employees get?",
        target_departments=["hr"],
    )
    assert decision.permitted
    assert "hr" in decision.permitted_departments


def test_admin_permitted_all_depts(rbac):
    for dept in ["hr", "finance", "legal", "technical", "medical"]:
        decision = rbac.check_access(
            user_id="admin1",
            user_role="admin",
            query="show me data",
            target_departments=[dept],
        )
        assert decision.permitted, f"Admin should be permitted for dept={dept}"


# ── Column rule tests ─────────────────────────────────────────────────────────

_EMPLOYEE_RULES = {
    "employees": {
        "salary": "BLOCK",
        "salary_grade": "ANONYMIZE",
        "full_name": "ALLOW",
        "ssn": "BLOCK",
    }
}

_SAMPLE_ROWS = [
    {
        "full_name": "Alice Smith",
        "salary": 95000,
        "salary_grade": "senior",
        "ssn": "123-45-6789",
    }
]


def test_block_rule_hides_column_value():
    governed, blocked, _ = apply_column_rules(_SAMPLE_ROWS, "employees", _EMPLOYEE_RULES)
    assert "salary" not in governed[0], "BLOCK column must not appear in governed row"
    assert "ssn" not in governed[0]
    assert "salary" in blocked
    assert "ssn" in blocked


def test_anonymize_rule_masks_column_value():
    governed, _, anonymized = apply_column_rules(_SAMPLE_ROWS, "employees", _EMPLOYEE_RULES)
    assert "salary_grade" in governed[0]
    assert governed[0]["salary_grade"] != "senior", "ANONYMIZE should not return raw value"
    assert "salary_grade" in anonymized


def test_allow_rule_returns_raw_value():
    governed, _, _ = apply_column_rules(_SAMPLE_ROWS, "employees", _EMPLOYEE_RULES)
    assert governed[0].get("full_name") == "Alice Smith"
