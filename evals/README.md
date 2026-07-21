# Aegis Evals

An **eval harness** tests the *quality and safety of the system's behavior* — not
"does the code run" (that's the unit tests), but "does the whole system govern and
answer the way it's supposed to." It's the safety net that catches regressions when
you change a model, a prompt, retrieval weights, or an access rule.

It comes in two tiers.

## Tier 1 — Deterministic governance evals (runs in CI) ✅

**What:** [`scenarios.yaml`](scenarios.yaml) is a data-driven list of governance
expectations — "an employee must never see this SSN", "this JOIN must not leak",
"a low-confidence internal question must refuse". [`run_evals.py`](run_evals.py)
executes each against the **real enforcement code** (RBAC firewall, row/column
rules, confidence routing, prompt guard).

**Why it can gate CI:** it uses no LLM, no network, and no API keys — so it's fast,
reproducible, and free. A failure means a governance guarantee regressed, which is
a security incident.

```bash
python evals/run_evals.py            # prints a per-category report; exit 1 on any failure
```

It also runs inside the normal test suite (`tests/unit/test_evals.py`) and as its
own CI step.

**Categories:** `column`, `join`, `rows`, `departments`, `routing`, `injection`.

**Add a case** by appending to `scenarios.yaml` — no code needed. This is designed
so a security or compliance reviewer can encode "this must never happen" as a
permanent, enforced check:

```yaml
- id: my-new-guarantee
  category: column
  desc: What this protects, in one line.
  role: employee
  table: payroll
  rows:
    - {employee_id: EMP1, net_pay: 71000}
  expect:
    blocked: [net_pay]
    forbidden_values: ["71000"]
```

## Tier 2 — Answer-quality evals (nightly / manual, NOT in CI)

**What:** Does the assistant give *correct, grounded* answers? "How many annual
leave days?" → the answer must contain the right number and cite the right source.

**Why it's not a CI gate:** it needs a live LLM + retrieval, which costs money and
isn't perfectly deterministic. Run it before releases or on a nightly schedule
against a running server, not on every commit.

**Design (for when you build it out):**
- A separate `answer_scenarios.yaml`: `{question, role, expect: {contains, cites, routing}}`.
- A runner that logs in via the API, calls `/api/v1/query`, and checks:
  - deterministic assertions (answer excludes an SSN regex, expected source cited,
    routing path) — these can be strict;
  - fuzzy correctness via keyword match or an **LLM-as-judge** (a second model
    grades answer-vs-expected) — report a score, don't hard-fail on small drift.
- Track pass-rate per category over time to catch quality drift from model/prompt
  changes.

The clean split is the point: **security-critical governance gates every commit for
free (Tier 1); subjective answer quality runs on a schedule (Tier 2).**
