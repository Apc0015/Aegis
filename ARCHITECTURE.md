# Aegis Architecture — the governance model, in plain language

This document explains **how Aegis keeps people from seeing data they're not
allowed to see**, written so a non-engineer can follow it. If you only read one
section, read ["The one big idea"](#the-one-big-idea).

---

## The one big idea

Most "chat with your company data" tools work like this: they give the AI
*everything*, let it find an answer, and then (maybe) try to hide the sensitive
parts of the answer afterward. That's backwards. Once the AI has read a salary or
a patient record, it's too late — the secret already left the vault.

**Aegis puts the lock on the vault door, not on the exit.** Before the AI is
allowed to read anything, a security layer we call the **data firewall** decides
what this specific person is cleared to see, and removes everything else. The AI
only ever receives data the asker was already allowed to see. There is nothing
sensitive for it to leak, because it was never handed anything sensitive.

Two principles make this trustworthy:

1. **Fail-closed.** When anything is unclear — an unknown job role, a
   mis-typed rule, an ambiguous database query — Aegis shows *less*, never more.
   The safe default is always "deny."
2. **No AI in the security decision.** The AI writes answers. It does **not**
   decide who's allowed to see what. Those decisions are made by fixed rules and
   plain code, so they're predictable and auditable. An AI can be talked into
   things; a rule table cannot.

---

## What happens when someone asks a question

Here is the life of a single question, from typing it to getting an answer:

1. **Sign in.** The user logs into the web console. Their identity and **role**
   (employee, manager, or admin) are carried in a signed token — they can't
   change their own role.

2. **Access check (the gate).** Before any searching happens, Aegis checks: is
   this role allowed to look in the area this question is about? An employee
   asking about the finance department is stopped right here. The denial is
   logged. Nothing was retrieved.

3. **Understand the question.** If the gate opens, Aegis figures out what the
   question is about (HR? legal? medical?) and rewrites it into a cleaner search —
   still no sensitive data touched.

4. **Retrieve — two ways.**
   - **Documents:** searches the indexed company documents the role is allowed to
     read, using two complementary search methods (meaning-based and
     keyword-based) for better recall.
   - **Database:** if the question needs structured data (e.g. "how many patients
     had appointments last month"), Aegis runs a **read-only** database query. It
     can never change or delete data — the connection is opened in read-only mode
     at the lowest level.

5. **The data firewall (the important part).** Every row and column that came
   back is filtered against the asker's rules:
   - **Block** — the column is removed entirely (e.g. an employee's request never
     includes anyone's Social Security number).
   - **Anonymize** — the value is masked into a safe description (e.g. an exact
     salary becomes "upper salary range").
   - **Allow** — the value passes through.

   Only the surviving, cleaned data moves forward.

6. **Write the answer.** *Now* the AI is brought in, and only now. It receives
   the already-filtered data and writes a natural-language answer. It literally
   cannot mention a blocked column, because it never received it.

7. **Confidence check & routing.** Aegis scores how well-supported the answer is
   and picks a response style:
   - **Direct** — confident, well-grounded answer.
   - **Disclaimer** — answer with a caution that it may be incomplete.
   - **Web fallback** — for general (non-confidential) questions, it may consult
     the public web instead of guessing.
   - **Refuse** — if it can't answer safely, it says so rather than inventing.

8. **Audit.** The whole event — who asked, what was allowed, what was blocked or
   anonymized, how long it took — is written to the audit log and can be exported.

---

## The three layers of access control

Access isn't one switch; it's three cooperating checks. A piece of data must
survive **all three** to reach the asker.

| Layer | Question it answers | Example |
|---|---|---|
| **Department scoping** | *Are you allowed in this area at all?* | An employee can't retrieve from `finance`. |
| **Row-level security** | *Which records are yours to see?* | An employee sees only their own leave requests; a manager also sees their reports'. |
| **Column-level rules** | *Which fields of a record can you see?* | A manager sees salaries but not tax withholdings; an employee sees neither. |

**Row-level security is strict on purpose.** If a database result doesn't carry
proof of ownership (the record's owner ID), Aegis drops it rather than guess. This
closes a subtle leak where a cleverly-worded query could dump everyone's rows by
simply *not* asking for the owner column.

**Column rules are strictest-wins across JOINs.** When a database query combines
two tables, a column is governed by the *most restrictive* rule found in *any* of
the tables involved. So a permissive "reference" table can never be used as a side
door to smuggle a sensitive column out of a protected table.

---

## Why "fail-closed" matters

Security rules are only as good as their worst-case behavior. Aegis is built so
that **every ambiguous situation resolves toward denial**:

- An **unknown role** (not one of employee/manager/admin) gets **nothing** — not
  even public content.
- A **mis-typed or wrong-type rule** in the config (say `"Block"` instead of
  `BLOCK`, or a number where a rule word should be) is treated as **BLOCK**, not
  quietly ignored.
- A database result with **no clear owner** is **dropped**.
- A generated database query that isn't a single, read-only `SELECT` is
  **rejected** before it runs.

This behavior isn't just hoped-for; it's pinned down by an automated test suite
(the RBAC edge-case tests) that runs on every change as a required gate. If a
future change accidentally opens one of these doors, the build fails.

---

## Where the rules live

- **`config/access_rules.yaml`** — the human-editable rulebook: which document
  categories each role may read, and the per-table, per-column `ALLOW` /
  `ANONYMIZE` / `BLOCK` rules. This is where a security or compliance lead tunes
  who-sees-what.
- **`src/aegis/config.py` (`RBAC_ROLES`)** — each role's department scope and
  capabilities (e.g. who may delete documents or export the audit log).

Changing access is a config edit, not a code change — and the tests re-verify the
fail-closed guarantees against whatever the config says.

---

## The moving parts (for the technically curious)

| Component | Responsibility |
|---|---|
| `src/aegis/rbac/rbac_module.py` | The data firewall: department, row, and column enforcement. Fail-closed. |
| `src/aegis/rbac/audit_log.py` | Append-only audit trail (its own database, separate from company data). |
| `src/aegis/core/department_router.py` | Deterministic, keyword-based routing — no AI in the security path. |
| `src/aegis/core/db_pipeline.py` | Read-only database access + text-to-SQL validation. |
| `src/aegis/agents/` (R1–R4) | Classify → Rewrite → Retrieve → Summarize, plus confidence scoring. |
| `src/aegis/connectors/` | Bring documents in from Gmail, Drive, OneDrive, SharePoint, Slack, local disk. |
| `api/` | The FastAPI backend and its authenticated endpoints. |
| `aegis_web/` | The React web console. |

The audit log deliberately lives in a **separate database** from the company data.
The company database is only ever opened **read-only**; the audit log is the one
place Aegis writes — and it only ever appends.

---

## In one sentence

Aegis answers questions about your company's data while guaranteeing — by
construction, deterministically, and fail-closed — that each person only ever
sees what their role permits, with every decision logged.
