# H_SLOW PostgreSQL integration check

Date: 2026-09-12. This is local test evidence for the disabled H_SLOW planning
adapter. It is not broker evidence, deployment approval, an account selection,
or a milestone-completion claim.

## Isolated test surface

An explicitly created disposable `postgres:17.6-bookworm` container used a
fresh database named `forex_hslow_adapter_test`. It had no host mounts and no
access to an existing database. PostgreSQL was published only as an ephemeral
`127.0.0.1` port for the temporary `psycopg` test process. The container was
removed after verification. No credential, account identifier, broker request,
MT5 call, or retained raw database output is recorded here.

## Observed results

After applying `sql/h_slow_lifecycle.sql`, actual output from a real planner →
`HSlowLifecycleStore` → PostgreSQL sequence was:

```text
persisted=PENDING
claimed=CLAIMED
unknown=SUBMISSION_UNKNOWN
restart_claim=None
different_intent_blocked=True
first_terminal=TERMINAL_RECONCILED
second_claimed=CLAIMED
second_terminal=TERMINAL_RECONCILED
```

This demonstrated durable persistence, conditional atomic claim, no retry of
an unknown submission after a new store instance, explicit terminal
reconciliation, and rejection of a different intent for the same unresolved
opaque account scope. A subsequent negative SQL control also rejected an
`OPEN` row with a null direction after the schema's null-check correction.

## Reproduction boundary

### Pending-entry expiry extension

A subsequent fresh disposable PostgreSQL 17.6 check exercised the expiry
schema and adapter, including a real row-lock wait crossing the entry deadline.
Seven integration cases passed: original lifecycle, expiry/no-reclaim and
append-only expiry audit, preservation of undated/close/unknown work, migration
reapplication with retained rows/custom constraints, non-UTC database session
timezone normalization, row-lock deadline refusal, and rollback of a claim
whose account-uniqueness-index wait crossed the deadline. Together with the
worker/persistence unit tests, 28 targeted checks passed. Separate read-only
review independently repeated the final correction. The disposable container
and its test database were removed after verification. This remains local
engineering evidence, not deployed recovery or broker proof.

`tests/integration/test_h_slow_postgres.py` is deliberately opt-in. It needs a
loopback `FOREX_H_SLOW_TEST_DSN`, a database name beginning `forex_hslow_`, and
`FOREX_H_SLOW_ALLOW_SCHEMA_RESET=YES`; it then drops and recreates only that
test database's `forex` schema. It has no default DSN, does not run in the
normal test suite, and must never be pointed at a deployed or shared database.

This verifies only the local PostgreSQL persistence surface. A separately
approved deployment, account binding, broker reconciliation adapter and
real-world Demo evidence remain required.
