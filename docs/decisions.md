# Architectural decisions

## ADR-001 — Lightweight milestone governance

Use transition contracts, explicit state, evidence, and sign-off without importing the Autonomous Framework controller and agent hierarchy.

## ADR-002 — Shared transport, app-owned adapter

The reusable T480 transport core belongs to `cs-ai-lab-infra`. Forex owns its fixed catalog, wrapper, application behavior, and evidence.

## ADR-003 — Configuration-first with hard safety bounds

Human-changeable non-secret values use YAML. Secrets and machine-local values use environment or ignored local files. Schema and code prevent configuration from enabling live trading, the live server, orders, or agent authority.

## ADR-004 — Evidence and verification are separate

Capture retains raw observations. An independent verifier checks them without contacting or repairing the observed system.

## ADR-005 — Completion is observed, not scheduled

`target_date` is a forecast. Only the closeout-generated UTC `proven_at` is an actual completion timestamp.

## ADR-006 — Shared database service, Forex-owned data boundary

Use the private PostgreSQL + pgvector service on the T480 managed by
`cs-ai-lab-infra`; do not introduce a Forex-specific database stack. Forex owns
the `forex` schema, migrations, fixed adapter, historical-data contracts, and
evidence. The shared platform owns transport, Docker, credentials, backups,
and network exposure.

## ADR-007 — Review Board only at phase gates

The only formal review body is the Review Board: Triad plus Financial Domain
Expert. It is required at M16, M27, and M32, not for every MVP milestone.
Routine work closes through tests, the milestone's declared real-world check
where applicable, and explicit human sign-off. Builder/Reviewer handoff
machinery and automated reviewer runners are deliberately excluded.
