# Aegis — Product context

## What it is
An authenticated operator console for an enterprise RAG system with a role-based
**data firewall**. Users (admin / manager / employee at a medical company) ask
questions through a governed pipeline: RBAC decides what they can reach, retrieval
pulls documents + database rows, a firewall converts raw sensitive data into a
role-scoped summary, and every query is audited.

## Register
Product. Design serves the task. Bar = "earned familiarity" — a user fluent in
Linear / Stripe / Raycast should trust it instantly. The tool disappears into the
work.

## Who / where / mood (scene)
A security- and compliance-minded operator at a desk during a workday, running
sensitive internal queries for extended sessions. Mood: calm, precise control-room
confidence. Not playful, not flashy, not a neon terminal. Trustworthy and exact.

## Primary surfaces
Login · Chat (streaming, the core loop) · Dashboard · Documents · Projects ·
Audit (admin) · Admin (admin) · Settings.

## Design north stars
- **Governed by design.** The firewall / RBAC is the product's soul; surface it as
  meaningful signal (blocked / anonymized columns, access verdicts, routing), not
  decoration.
- **Precision over decoration.** Dense where it helps, quiet everywhere else.
- **Machine data reads as machine data.** IDs, models, latencies, tokens, verdicts
  in mono; human language in sans.
