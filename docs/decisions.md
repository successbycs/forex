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
