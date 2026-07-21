# Decisions Log

This file records what changed to turn Aegis from a capstone project into a
shipping product, and **why**. It's written for a non-engineer — each entry says
what we did, the reasoning, and the trade-off we accepted.

Context: Aegis began life as a graduate capstone (previously named "RAPID"). The
core engine was already strong — governed RAG with a real data firewall. The work
below productizes around that core: it removes the academic framing, hardens the
security, makes the deployment real, and rewrites everything user-facing around
one promise — *"Ask your company's data. See only what you're allowed to."*

---

## Product & scope

### D-1 — Kept the proven core untouched
**Decision:** We did **not** rewrite the governance engine. The RBAC module,
deterministic department router, R1–R4 agent pipeline, confidence scorer, audit
log, and connectors were treated as proven and built *around*, not replaced.
**Why:** They already implement the hard part correctly (fail-closed, JOIN-safe,
row-level ownership). Rewriting proven security code introduces risk for no gain.
**Trade-off:** We inherit the existing design; improvements were made as targeted
hardening, not a redesign.

### D-2 — Kept all five external connectors
**Decision:** Gmail, Google Drive, OneDrive, SharePoint, and Slack all stay in v1.
**Why:** Founder call. All five are real, working implementations (not stubs), so
cutting them would remove genuine capability only to shrink surface area. For a
"plug in your data" product, breadth of sources is a feature.
**Trade-off:** Five OAuth integrations to keep maintained and secured. Accepted.

### D-3 — Kept the medical sample dataset, clearly labeled
**Decision:** The bundled demo stays a fictional 500-employee healthcare company
(patients, `patient_pii`, `hipaa_access_logs`, payroll), rather than being
generalized to a neutral industry. It is now **explicitly labeled as sample data**
everywhere it surfaces.
**Why:** Founder call, and it's the strongest possible demonstration of the
firewall — "block this patient's PHI" is far more vivid than "hide a number." It
also matches Aegis's strongest-fit verticals (healthcare, finance, legal).
**How we labeled it:** a new `AEGIS_DEMO_MODE` flag (default on) drives a "sample
data" notice in the console dashboard; the seed script prints a clear
"fictional / demo data only" banner; the README has a dedicated *Sample data*
section. A real deployment sets `AEGIS_DEMO_MODE=false`.
**Trade-off:** None meaningful — it reads as "a healthcare org with normal
departments," and the `documents/` folder was already generic-corporate.

---

## Removing the academic / RAPID past

### D-4 — Deleted the capstone document and academic artifacts
**Decision:** Removed `RAPID_Capstone_Final_Ayush_Chhoker.docx` (a full graduate
thesis with university, course, and mentor references) and reset stray personal
run-time state (a developer's saved query history, a stale learned Q&A entry).
**Why:** This ships as a real product; nothing should read as a school assignment.
**Trade-off:** The thesis is preserved in git history if ever needed; it's just no
longer part of the product.

### D-5 — Renamed the internal `rapid_` prefix to `aegis_`
**Decision:** The search indexes were internally named `rapid_<name>` (a leftover
from the old product name, which is now a *different* product). Renamed the prefix
to `aegis_` across the code, and regenerated the indexes.
**Why:** "RAPID" is the name of a separate product; carrying its name inside Aegis
is both confusing and off-brand. A repo-wide search for "rapid" now comes back
clean.
**Trade-off:** Existing local indexes had to be rebuilt once (they're regenerated
from source documents anyway, so this is a non-event for users).

### D-6 — Retired the old R.A.P.I.D. tagline
**Decision:** The app subtitle and API description literally spelled out
"RAG Application for Private Instant Deployment" — the old acronym. Replaced with
the Aegis motto and a plain description of what the product does.
**Why:** Same as D-5 — remove the old identity from anything a user or buyer sees.

---

## Security hardening (product-grade pass)

The core was already fail-closed in the tested cases. This pass verified it holds
in the *untested* edge cases the brief called out, and closed a few gaps.

### D-7 — Unknown roles now fail closed everywhere
**Decision:** An unrecognized role previously could still be granted access to the
always-public `general` area by one code path. Now an unknown role gets **nothing**
at every enforcement point.
**Why:** "Fail-closed on every unrecognized role" is a stated requirement. Even
though the sign-in gate already blocks unknown roles, defense-in-depth means the
downstream layer must not assume that.

### D-8 — Read-only database guard confirmed on every path; MySQL hardened
**Decision:** Verified that **every** place a company-data query runs opens a
read-only connection. SQLite uses an OS-level read-only mode; PostgreSQL uses a
read-only session; MySQL had no equivalent, so we added an explicit read-only
session (and fail closed if the server refuses it). The audit log — which must
write — was confirmed to live in a *separate* database, as intended.
**Why:** "Confirm the read-only DB guard is real everywhere a query can run."

### D-9 — Stricter validation of AI-generated SQL
**Decision:** Added a single, central validator for AI-generated database queries
that rejects anything that isn't one read-only `SELECT` — including "stacked"
queries (a second statement hidden after a semicolon) and any write keyword.
**Why:** Defense-in-depth. Even though the read-only connection already blocks
writes, rejecting suspicious queries *before* they run is a cheaper, clearer line
of defense.

### D-10 — Expanded the RBAC edge-case test suite and made it a CI gate
**Decision:** Added ~30 tests (`tests/unit/test_rbac_edge_cases.py`) covering:
missing/unknown roles, malformed and wrong-type rules, a column allowed in one
JOINed table but absent from another, empty table contexts, and the SQL validator.
Wired a GitHub Actions workflow so this suite must pass before anything merges.
**Why:** "Expanded RBAC edge-case test suite passes and is a CI gate" is in the
definition of done. Tests turn "we believe it's fail-closed" into "the build
proves it, on every change."
**Result:** Full unit suite (129 tests) green.

---

## Making the deployment story real (not aspirational)

### D-11 — Fixed a fresh-clone bug: the server couldn't import its own code
**Decision:** Following the documented steps, `uvicorn api.main:app` failed with
`No module named 'aegis'`, because the package lives in `src/` and was never
installed. Added `pip install -e .` to the install steps (and to the Docker image).
**Why:** "Verify the deployment story is real." A fresh clone must actually run.
This was the single biggest gap — the app worked on the original developer's
machine only because of a test-only path setting.

### D-12 — Added a real Docker Compose deployment
**Decision:** Added `Dockerfile` (API), `aegis_web/Dockerfile` + `nginx.conf`
(web console), a `docker-compose.yml` tying them together, and a container
entrypoint that seeds the sample data and builds indexes on first boot. So
`cp .env.example .env && docker compose up` stands up the whole product.
**Why:** IT / security / compliance buyers expect a containerized deploy. Docker
wasn't previously documented, so we built it as a first-class path.
**Honesty note:** The Compose configuration is validated (`docker compose config`
passes) and the Dockerfiles/entrypoint are standard and correct, but the container
**images were not built in this environment** (no Docker daemon available here).
The **local (venv) path is fully verified end-to-end** — see D-14. Build the
images in your own environment to confirm before relying on the Docker path in
production.

### D-13 — Fixed stale configuration that blocked a clean run
**Decision:** The developer's local environment file used the old `RAPID_` prefix
for settings the renamed code reads as `AEGIS_`; the dev-server launch config
pointed the web console at the wrong API port. Both fixed. Added `AEGIS_DEMO_MODE`
to the example environment file.
**Why:** Small stale-config gaps are exactly what make a "documented" deploy fail
in practice.

### D-14 — Verified the running product end-to-end
**Decision:** Booted the API + web console locally and confirmed, in a browser:
sign-in works; the console reports all systems operational with the database
connected read-only and all ten document indexes loaded; the "sample data" notice
appears; and the audit log shows real access decisions (an employee correctly
**denied** finance access).
**Why:** "Confirm it actually stands the product up cleanly." Verified, not
assumed.

---

## Honesty & accuracy in the docs

### D-15 — Stated the real database support level
**Decision:** The docs now say **SQLite is the validated backend** for v1;
PostgreSQL/MySQL are marked **experimental**.
**Why:** SQLite is what the product is tested and demoed on, and its read-only
guard is OS-enforced. The other backends are wired but not yet validated
end-to-end. Claiming parity would be aspirational — exactly what we were asked to
avoid.

### D-16 — Rewrote all user-facing copy around the motto
**Decision:** README, login screen, dashboard, and API description now lead with
*"Ask your company's data. See only what you're allowed to."* and describe Aegis
as governed enterprise RAG. Removed every capstone/student framing. Added
`ARCHITECTURE.md` (governance in plain language) and this file.
**Why:** Definition of done: "README, onboarding, and UI copy reflect only the
motto/goal/use case."

---

## What we deliberately did **not** add

Aegis answers questions safely. It is **not** a workflow or decision-tracking tool.
We deliberately kept out — and would reject in review — meetings, action items,
decision owners, follow-through tracking, CRM records, multi-tenancy, agent-mesh
orchestration, bidding, and C-suite hierarchy. Those belong to a different product.
Aegis stays a horizontal, plug-in-your-data governed-RAG product.
