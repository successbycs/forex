# Independent incident-repair review

Reviewer: separate read-only agent `incident_repair_review`, September 23, 2026.
Implementer: primary agent. Chris explicitly approved the precise loss-preserving
accounting exception, commit and deployment; review is not operator approval.

The reporting review found masked pauses and stale readiness claims. Those were
repaired and covered by full/compact view, heartbeat projection and complete
assessment-path tests.

Accounting review required two repairs: refuse existing ownership via broker
order references even when position metadata is null, and verify the original
raw evidence digest before application. Both are implemented and re-reviewed.
Final reviewer result: no remaining code-review blocker in the fixed package.
Anchors and unrelated pauses are preserved; replay cannot apply the loss twice.
Actual application and subsequent readiness remain operational checks.

Reviewed SQL SHA-256:
`cc1fbc5b82f40364c2105e2512cf531fcc5e121d42a54477a15dd25be5d4510a`.
Reviewed observation validator SHA-256:
`c97a558ce2371efe5a65c1406d0a6ac16d1d374ae6f6370ebe81485150890709`.

Verification: isolated PostgreSQL16 tests apply/replay the real SQL and prove
immutability, unchanged anchors/other pauses, rollback on changed state and
existing ownership. A PostgreSQL scoreboard fixture verifies MATCHED/REPAIRED
outcomes count and unresolved P&L does not. All 24 incident tests pass; all 28
PostgreSQL adapter tests pass. The earlier 220 reporting/runner/service tests
also passed before the new adapter tests were added.

Measured encoded T480 commands: account identity 4338, status 6910, prepare
4142, install 7134, enable hold 2094, disable hold 1002 characters. New fixed
incident stage/apply/verify bodies also pass the less-than-7500 regression.
Payload fragments and final verifiers must pass sizing before actual staging.

Pre-deployment sizing caught runner fragments at 7726 characters. Removing
the unused payload variable and constructing the same fixed release root
directly reduced the maximum to 7490. Independent reviewer confirmed unchanged
source binding, all 96 fragment names/content and assembly/hash verification.
All nine focused transport/install/account checks pass, including a new check
of every registered release fragment. No oversized command was sent.
