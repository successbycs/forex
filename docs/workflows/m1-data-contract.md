# M1 data contract

## Purpose and status

This contract defines the minimum durable records required to trace an EUR/USD M1 Demo decision from observed data to reconciliation. It is a Wave 1 design contract: it documents target fields and invariants for later authorised changes. It does not change the listener, database schema, schedule or broker authority.

The current system retains many of these fields in M20 proposals, snapshots and audit tables. It does not yet guarantee one terminal decision per completed candle. A field marked **required** is required before that future claim can be made; it is not a claim that every historical artifact has it.

## Authority boundary

This contract applies only to `GOMarketsMU-Demo` and `EURUSD`. It grants no Live, generic broker, SQL, orchestration or schedule authority. Prefect and n8n may coordinate approved data work later; neither may submit, retry or reconcile broker orders. The listener/monitor remains responsible for broker protection and lifecycle recovery.

## Canonical identity

| Identity | Meaning | Requirement |
| --- | --- | --- |
| `candle_key` | Account/server, symbol, timeframe, completed candle close UTC | Required for one-candle decision accounting; no configuration version in the key |
| `decision_key` | `candle_key` plus immutable decision-contract version | Required for the durable terminal outcome; unique for executable M1 evaluation |
| `proposal_id` | Existing immutable proposal identity | One proposal may bind the decision; a refusal may have no proposal when no valid snapshot exists |
| `attempt_id` | Existing broker submission identity | At most one per executable proposal |
| Broker order, position and deal IDs | Broker-derived identities | Required for exact attempt/lifecycle/outcome joins when a broker action occurs |
| `pipeline_run_id`, `request_key` | Approved data-pipeline run and idempotency identity | Required only for an orchestrated source/projection path; never a trade identity |

`candle_key` makes repeated quote polls, restart, or configuration reload unable to create a second executable decision for the same closed M1 candle. Research or replay records use a separate non-executable namespace.

## Required time and provenance fields

Every source-derived record preserves:

| Field | Meaning |
| --- | --- |
| `source_observed_at_utc` | When publisher/broker says the observation occurred |
| `received_at_utc` | When this system actually received the bytes |
| `available_at_utc` | Earliest time valid for a decision; never later inferred backwards |
| `decision_cutoff_utc` | Boundary at which the decision evaluated available data |
| `persisted_at_utc` | When the durable application fact was accepted |
| `reconciled_at_utc` | When an exact broker lifecycle/outcome join was evaluated |
| `source_reference`, `source_sha256` | Immutable retained input location and digest |
| `contract_version`, `application_revision`, `configuration_fingerprint`, `strategy_version` | Version lineage without changing `candle_key` |

Raw bytes and their acquisition receipt remain immutable. PostgreSQL stores validated facts plus reference/digest; it is not the only copy of raw input.

## Terminal decision or refusal

For every completed M1 candle that reaches the decision acquisition deadline, retain exactly one of:

- a durable `BUY`, `SELL`, or `NO_TRADE` decision with its snapshot, selected owner or no-owner reason; or
- an explicit **operational refusal** when a valid decision snapshot cannot be formed, including known identity/provenance and stable reason code.

Do not fabricate a proposal merely to represent a failed acquisition. Missing, stale, inconsistent or ambiguous inputs are safe refusals. A later historical record cannot cause an order for an expired candle.

An actionable decision requires exactly one selected owner. Zero owners is `NO_TRADE`. Risk, cost, calendar or account vetoes may turn an otherwise actionable candidate into `NO_TRADE`; they cannot invent a direction or owner.

## Idempotency, retries and recovery

The durable store enforces the executable `decision_key` and existing proposal/attempt reservation constraints. Repeated delivery, concurrent workers, restart, and timeout-after-commit must have one logical effect. A source revision is a new observed version, not permission to modify raw history.

Safe data retention/projection steps may have bounded retries. Invalid input ends visibly with a refusal. Notification delivery is not a projection success criterion. A timeout or unknown broker response never triggers an orchestrator retry; it enters the fixed reconciliation path. Database unavailability blocks new unjournaled entries but must not suppress protective monitoring or exits.

## PostgreSQL projection and joins

The existing M20 audit model contains sessions, proposals, decision snapshots, execution attempts, position events and outcomes. Future approved migration work adds only the smallest necessary contract fields/constraints and provides a read-only completeness report joining:

    raw receipt → canonical source fact → decision/refusal → proposal
      → attempt → broker position/deals → outcome/reconciliation

Joins use declared identifiers, not timestamp, price or comment guesses. Unmatched rows, unknown costs, revised source data and unresolved broker state remain explicit report results.

## Minimum completeness metrics

For each declared UTC interval, report:

| Metric | Definition |
| --- | --- |
| Expected facts | Count derived from source cadence, market session and observed uptime rules |
| Observed/retained facts | Count with valid immutable receipt and digest |
| Accepted/rejected projection | Valid PostgreSQL facts versus explicit validation refusals |
| Duplicate logical effects | More than one record for a uniqueness key; source revisions separate |
| Capture and projection lag | `received_at_utc - source_observed_at_utc` and `persisted_at_utc - received_at_utc` where available |
| Backlog | Valid retained facts not yet terminally projected at report time |
| Write failures | Terminal reason and affected identities, never silently dropped |
| Join coverage | Exact decision-to-attempt-to-outcome links and unresolved reasons |

Market closures, declared listener downtime and absent source publication are expected absences only when evidence identifies them. Otherwise report `UNKNOWN`, not zero missing facts.

## Higher timeframes and timeframe extension

M5/H1 are current shadow context. They need raw references and real receipt/availability times but cannot veto an M1 entry merely by being absent. M15 remains paused. Any later M15 authority requires its own timeframe key, point-in-time inputs, strategy contract, duplicate protection, tests, approved scope and evidence; it cannot reuse M1 authority implicitly.

## Acceptance for a future implementation

The contract is satisfied only when focused tests and a declared real capture show: one terminal outcome per eligible candle; no duplicate effect after replay/restart/concurrency; explicit refusal for unavailable input; retained raw provenance; exact broker joins where an order occurs; and continuing protective monitoring during pipeline/database outage. Tests alone do not prove continuous capture, broker availability or trading profitability.
