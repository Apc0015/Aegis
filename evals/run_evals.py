#!/usr/bin/env python3
"""
Aegis eval harness — deterministic governance evaluation (Tier 1).

Runs the scenarios in scenarios.yaml against the REAL enforcement code (RBAC
firewall, row/column rules, confidence routing, prompt guard). No LLM, no network,
no API keys — so it's fast, reproducible, and safe to run as a CI gate.

Each scenario asserts an expected governance outcome ("an employee must never see
this SSN", "a low-confidence internal question must refuse"). A failure here means
a governance guarantee regressed — treat it as a security incident.

Usage:
    python evals/run_evals.py [path/to/scenarios.yaml]

Exit code 0 if every scenario passes, 1 otherwise.

Tier 2 (answer quality — groundedness, correctness) needs a live LLM and is NOT
run here; see evals/README.md.
"""
import sys
import json
from pathlib import Path

import yaml

# Make the aegis package importable whether or not it's pip-installed.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aegis.rbac.rbac_module import (
    RBACModule,
    apply_column_rules,
    apply_column_rules_multi,
    apply_row_filter,
    load_column_rules,
)
from aegis.agents.confidence_scorer import decide_route, route_label
from aegis.prompt_guard import scan_for_injection, neutralize
from aegis.config import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM

ACCESS_RULES = str(ROOT / "config" / "access_rules.yaml")


class Fail(Exception):
    """Raised with a human-readable reason when a scenario's expectation is unmet."""


def _stringify(rows) -> str:
    return json.dumps(rows, default=str)


def _check_forbidden(governed, forbidden_values):
    blob = _stringify(governed)
    for v in forbidden_values or []:
        if str(v) in blob:
            raise Fail(f"forbidden value {v!r} leaked into governed output")


def _eval_column(s):
    rules = load_column_rules(ACCESS_RULES, s["role"])
    governed, blocked, anonymized = apply_column_rules(s["rows"], s["table"], rules)
    _assert_column_outcome(s, governed, blocked, anonymized)


def _eval_join(s):
    rules = load_column_rules(ACCESS_RULES, s["role"])
    governed, blocked, anonymized = apply_column_rules_multi(s["rows"], s["tables"], rules)
    _assert_column_outcome(s, governed, blocked, anonymized)


def _assert_column_outcome(s, governed, blocked, anonymized):
    exp = s["expect"]
    for col in exp.get("blocked", []):
        if col not in blocked:
            raise Fail(f"expected column {col!r} to be BLOCKED, blocked={blocked}")
    for col in exp.get("anonymized", []):
        if col not in anonymized:
            raise Fail(f"expected column {col!r} to be ANONYMIZED, anonymized={anonymized}")
    for col in exp.get("allowed", []):
        if not governed or col not in governed[0]:
            raise Fail(f"expected column {col!r} to be ALLOWED (present in output)")
    if exp.get("empty_row"):
        if any(row for row in governed):
            raise Fail(f"expected an empty governed row, got {governed}")
    _check_forbidden(governed, exp.get("forbidden_values"))


def _eval_rows(s):
    filtered = apply_row_filter(s["rows"], s["table"], s["user_id"], s["role"])
    exp = s["expect"]
    if "kept" in exp and len(filtered) != exp["kept"]:
        raise Fail(f"expected {exp['kept']} row(s) kept, got {len(filtered)}: {filtered}")
    match = exp.get("kept_match")
    if match:
        for row in filtered:
            for k, v in match.items():
                if row.get(k) != v:
                    raise Fail(f"kept row {row} does not match {match}")


def _eval_departments(s):
    allowed, denied = RBACModule().authorize_departments(s["role"], s["request"])
    exp = s["expect"]
    if set(allowed) != set(exp.get("allowed", [])):
        raise Fail(f"allowed {sorted(allowed)} != expected {sorted(exp.get('allowed', []))}")
    if set(denied) != set(exp.get("denied", [])):
        raise Fail(f"denied {sorted(denied)} != expected {sorted(exp.get('denied', []))}")


def _eval_routing(s):
    high = s.get("confidence_high", CONFIDENCE_HIGH)
    medium = s.get("confidence_medium", CONFIDENCE_MEDIUM)
    is_external = bool(s.get("is_external", False))
    verdict, refuse = decide_route(s["score"], high, medium, is_external)
    got = route_label(verdict, refuse, is_external)
    want = s["expect"]["route"]
    if got != want:
        raise Fail(f"score={s['score']} routed to {got!r}, expected {want!r}")


def _eval_injection(s):
    exp = s["expect"]
    finding = scan_for_injection(s["text"])
    if finding.detected != bool(exp["detected"]):
        raise Fail(
            f"detected={finding.detected} (patterns={finding.patterns}), expected {exp['detected']}"
        )
    removes = exp.get("neutralized_removes")
    if removes:
        cleaned, _ = neutralize(s["text"])
        if removes in cleaned:
            raise Fail(f"neutralize did not remove {removes!r}")


_DISPATCH = {
    "column": _eval_column,
    "join": _eval_join,
    "rows": _eval_rows,
    "departments": _eval_departments,
    "routing": _eval_routing,
    "injection": _eval_injection,
}


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / "scenarios.yaml"
    data = yaml.safe_load(path.read_text())
    scenarios = data.get("scenarios", [])

    passed, failed = [], []
    by_cat: dict = {}

    for s in scenarios:
        cat = s.get("category", "?")
        by_cat.setdefault(cat, [0, 0])  # [passed, total]
        by_cat[cat][1] += 1
        runner = _DISPATCH.get(cat)
        try:
            if runner is None:
                raise Fail(f"unknown category {cat!r}")
            runner(s)
            passed.append(s["id"])
            by_cat[cat][0] += 1
        except Fail as e:
            failed.append((s["id"], str(e)))
        except Exception as e:  # a crash in enforcement is itself a failure
            failed.append((s["id"], f"error: {e}"))

    print("=" * 70)
    print("AEGIS GOVERNANCE EVALS")
    print("=" * 70)
    for cat in sorted(by_cat):
        p, t = by_cat[cat]
        mark = "✓" if p == t else "✗"
        print(f"  {mark} {cat:<12} {p}/{t}")
    print("-" * 70)
    if failed:
        print(f"FAILED {len(failed)}/{len(scenarios)}:\n")
        for sid, reason in failed:
            print(f"  ✗ {sid}\n      {reason}")
        print("=" * 70)
        return 1
    print(f"PASSED {len(passed)}/{len(scenarios)} — all governance guarantees hold.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
