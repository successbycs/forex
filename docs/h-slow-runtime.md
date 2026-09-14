# H_SLOW runtime integration

The runtime evaluator connects a retained research decision, an isolated stream
registry and a timed reconciliation observation to the lifecycle planner:

```text
python3 scripts/h_slow_runtime.py /path/to/evaluation.json
```

The JSON object supplies `research_decision`, `stream_registry`, `envelope`,
`evaluated_at_utc` and `maximum_observation_age_seconds`. An optional
`trial_mandate` is validated as a pre-activation record. The envelope contains:

```json
{
  "schema_version": "forex.h-slow.timed-observation.v1",
  "observed_at_utc": "2026-09-01T00:00:10Z",
  "received_at_utc": "2026-09-01T00:00:11Z",
  "observation": {}
}
```

`observation` must contain the full lifecycle observation schema defined in
`src/forex/h_slow_lifecycle.py`; the empty object above is a structural example,
not valid operational input. Supply the configured age threshold explicitly
from the eventual deployment policy. No production default is implied.

Observed time must follow the research decision and precede receipt, and receipt
must precede evaluation. Age is measured from observation, not receipt. The
monthly target must still belong to the evaluation's UTC month. Unknown
reconciliation or pending attempts still produce WAIT with fresh clocks.

The command returns JSON, hashes the observation envelope, and preserves input
files. Errors return exit code 2 with no result on stdout. Duplicate JSON keys
and nonfinite constants are refused. All output has execution authority false.

### Local readiness report

`python3 scripts/h_slow_readiness.py /path/to/readiness.json` is a pure local
connection check for one retained snapshot. Its closed input schema combines
the runtime inputs above with `market_inputs`, `limits`, `event_eligibility`
and `primary_context`. It evaluates the existing runtime/lifecycle plan and
then the disabled preparation boundary, returning one hash-bound report.

The command does not import the worker, persistence adapter, PostgreSQL,
terminal, MT5, scheduler or network client. A current unavailable primary
event context is a successful local report with `readiness_state:
NO_NEW_ENTRY`, not a fabricated clear calendar or an error-recovery action.
`PREPARED_DISABLED_NO_ROUTING` remains calculation readiness only; it is not
an account selection, deployment, worker start or order permission.

### Durable preparation worker

`forex.h_slow_worker.run_h_slow_worker_once` joins this evaluator to an
explicitly supplied `HSlowLifecycleStore`. It checks the store's registry
binding before database access and reads unresolved H_SLOW intents across the
whole account scope, including earlier terminals/configurations. An unresolved
intent prevents a different decision from adding another plan. Replaying the
same plan returns its durable state. It never claims or submits an order.

The read-then-persist sequence is not an atomic scheduling reservation:
concurrent preparers can retain different PENDING plans. The separate SQL
account-wide claim constraint prevents concurrent unresolved claims. A future
router must reconcile and revalidate eligibility before claiming; preparation
is not execution permission.

The worker now binds new OPEN intents to the first instant of the next UTC
month. Before reading unresolved work it expires eligible never-submitted OPEN
intents using the database clock. Expiry is `EXPIRED_NOT_SUBMITTED`, retained
in a separate append-only expiry audit—not a broker response or a reconciliation.
Claiming locks the exact scoped row first, checks the wall clock and checks
again after the update, rolling back if an account-index wait crossed the
deadline. Database lock waits cannot extend the entry deadline. Replaying an expired
intent returns its terminal state; changing its deadline is refused.

CLOSE intents have no monthly-entry deadline. CLAIMED, SUBMISSION_UNKNOWN,
legacy undated intents and intents from another terminal/configuration are
not expired by this cleanup. They continue to block new account work until
their applicable reconciliation or reviewed migration is resolved. The worker
still validates its current runtime observation before housekeeping; the
store independently refuses expired claims even when cleanup has not run.
Expiry does not cancel broker orders, release broker exposure or abandon
management of existing positions.

### Explicit durable-worker command

`python3 scripts/h_slow_worker.py /path/to/retained-worker-input.json` is the
controlled command wrapper for the existing worker. It requires all runtime
input fields and a locally configured PostgreSQL DSN in
`FOREX_H_SLOW_DSN` (or another explicitly named `FOREX_H_SLOW_*` variable via
`--dsn-env`). It does not discover a database, accept a DSN argument, create a
schema, select an account, claim an intent, contact MT5, or submit an order.
Input files are read only. The command refuses before connecting when its
input or named environment variable is invalid.

The operator must apply `sql/h_slow_lifecycle.sql` to an explicitly selected
H_SLOW store before using this command. A successful invocation can persist a
disabled lifecycle intent, but always returns
`submission_status: DISABLED_NOT_ROUTED` and `execution_authority: false`.
It is deployment preparation, not H_SLOW activation or a substitute for the
required human account/limits/protection/holding mandate.

Apply the updated `sql/h_slow_lifecycle.sql` before deploying this worker: it
adds nullable deadline/expiry fields and the immutable expiry audit. Existing
rows are preserved without inventing deadlines; owned state constraints are
updated, while additional owner constraints remain intact. The package was
tested on disposable local PostgreSQL, not migrated into the trading database.

Integration requirements still outstanding:

- Supply actual account-bound broker and audit observations, with acquisition
  timestamps; caller declarations and digests do not establish authenticity.
- Integrate the existing persistence and atomic claim adapter with the actual
  router. Unresolved or unknown attempts must remain unavailable for retry.
- Bind sizing, protection, financing, holds, leases and the approved account
  route before order activation.
- Run protection and reconciliation independently of new-target evaluation.
  A stale observation or expired target raises an evaluation error; it must
  never disable management of an existing position.

These components run locally for retained-input evaluation. No remote runtime
or order route has been installed by adding them. Existing market-dependent
milestones remain pending under their original contracts.

### Disabled order preparation

`python3 scripts/h_slow_prepare.py /path/to/preparation.json` consumes
`lifecycle_plan`, `market_inputs`, `limits`, and for a directional `OPEN`, a
retained `research_decision`, a hash-bound `event_eligibility` record, and a
complete hash-valid `primary_context` report. The
module docstring in
`src/forex/h_slow_order_preparation.py` lists the closed field schemas.
Supply the protective stop, fresh Demo EUR/USD bid/ask, broker tick/volume/stop
constraints, AUD tick-loss value, per-lot notional/margin, free margin and a
known labelled adverse-cost allowance. No missing cost defaults to zero.

Preparation rounds a BUY stop down and a SELL stop up to the price tick, checks
the broker minimum distance from the closing side of the quote, and calculates
loss from the actual entry price to that rounded stop. Thus entry spread is
included once, alongside the supplied financing/fee/slippage allowance.
Volume rounds down under every explicit cap. Below-minimum size is refused.

This uses a 128-digit decimal context over bounded inputs (at most 18
significant digits; nonzero magnitudes from `1e-12` through `1e12`) and
rechecks all caps after volume quantization. Unsupported numeric inputs and
results that cannot round-trip exactly through JSON numeric output are refused.
It does
not manufacture an M22 simulation approval or invoke the MT5 executor.
Inputs are caller-declared, not verified broker observations. Hashes establish
binding, not authentication. Missing event context, unknown/partial/ambiguous/
unavailable coverage, an invalid digest, an annotation/source/primary-context
mismatch, or a
`NO_NEW_ENTRY` event result produces `REFUSED`. This H_SLOW boundary does not
implement or enable the Wave 2 event-risk policy; it only refuses to infer a
clear event result. The result is `PREPARED_DISABLED` or `REFUSED`,
never an executable order or activation approval. Ongoing position protection,
account/holding mandate, combined exposure reservation, actual broker margin
check and router integration remain outstanding.

### Snapshot-derived initial stop

The preparation command also accepts optional `protection_snapshot`. In that
mode omit `market_inputs.technical_stop_price`: the command derives it using
the proposed `config/h_slow_protection.json` ATR20 × 3 rule. It re-evaluates the
snapshot and requires its research-decision hash to match the lifecycle plan,
the OPEN direction to match, the quote to follow the decision and the decision
to remain in the evaluation month. For an annotated plan also supply the retained
`research_decision`: the command reconstructs and verifies its context attachment
before matching the full decision hash. Optional context is not a trading veto.
Explicit-stop preparation remains available separately.

The derived record retains its snapshot and input digests, rule, ATR and raw
technical stop alongside the disabled sizing result. The exact raw stop is
retained separately; the prepared stop rounds away from entry to 15 significant
digits before broker-tick rounding, preserving compatibility with the sizing
API's JSON numbers. Arithmetic uses a private 128-digit decimal context and
bounded price inputs. Snapshot-derived stop
calculation does not authenticate broker quotes or grant submission authority.
It adds no trailing-stop or overnight holding permission. Deployment and
ongoing protection of actual owned positions remain separate integration work.
