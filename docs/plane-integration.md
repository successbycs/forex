# Plane delivery-board integration

Plane is the visible task board for Forex delivery. It does not grant broker,
deployment, evidence, task-acceptance or milestone-closeout authority. The
repository remains the source of the implementation, acceptance checks and
formal proof.

## Current state

The integration is deliberately **offline preparation** while the Plane
instance is deployed by Planner. `config/plane_sync.json` contains no endpoint,
workspace, project identifier or secret. Those values are machine-local
environment variables (`FOREX_PLANE_*`) supplied only after a verified Planner
handoff.

`python3 scripts/plane_sync.py` validates the non-networking contract and maps
each stable active Harness/A/B/C task ID to a future Plane work item. It neither contacts
Plane nor changes a task, runtime state or trading authority.

## Operational contract after handoff

- Plane displays assignment, status, blocker, evidence references and review
  result. Its work-item identifier is stored with the queue package ID.
- An agent starts only a repository-defined task in `Ready`; it posts progress
  and evidence before requesting `Review`.
- `Done` requires repository acceptance evidence. A Plane-only state change is
  treated as an inconsistency and cannot satisfy a downstream dependency.
- The future synchronizer must be idempotent, redacted and fail safe: when
  Plane is unavailable it keeps the current bounded task running, records the
  pending update locally, and does not select new work or claim sync success.
- Plane credentials are secrets. MT5 credentials, order data and raw evidence
  never belong in Plane.

Plane connectivity and an end-to-end board demonstration remain Harness H5
acceptance work; this document is not evidence that they are complete.
