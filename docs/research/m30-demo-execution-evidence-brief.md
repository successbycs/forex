# Evidence Brief: M30 controlled Demo execution proof

## Decision

Decide whether to create an M30-specific proof workflow for one controlled
EUR/USD order on the declared GOMarketsMU-Demo surface.

## Proposed claim or hypothesis

If an eligible EUR/USD Demo proposal passes the existing fixed autonomous
safety gates, the fixed execution path can prove one entry, a bounded close, and
complete broker reconciliation without expanding broker authority. The test
does not claim a trading edge, profitability, or Live capability.

## Context

- Instrument / market: EUR/USD through the configured `EURUSD` broker symbol.
- Timeframes: a fresh tick and completed M1 bars; UTC is the evidence timezone.
- Data source: GOMarketsMU-Demo MT5 observations captured only through the
  fixed T480 adapter.
- Period examined: the one M30 operation after approval; no historical return
  is used to justify the order.
- Intended use: formal Demo-only operational proof for M30.
- Known constraints: the listener currently reports `MAINTENANCE_HOLD`; no
  order, hold release, or other remote mutation is authorised by this brief.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| `milestone_registry.json`, M30 contract | Project contract | Requires a bounded autonomous Demo entry within existing safety limits, mandatory close or earlier risk exit, complete reconciliation, and 24-hour current evidence. | Directly defines M30 proof. | Does not itself provide a broker observation. |
| `t480/m20_demo_trading_session.py` | Fixed executor source | Builds a proposal, reserves it, submits only to Demo EURUSD, records opening/closing events, and reconciles outcomes. | Existing bounded execution and reconciliation path. | Its invocation can place an order and it does not retain an M30 evidence bundle. |
| `scripts/capture_m20_demo_evidence.sh` and `scripts/m20_demo_evidence_contract.py` | Evidence tooling | Captures raw fixed-operation output and validates server, symbol, provenance, and reconciliation without broker contact during verification. | Reusable pattern for M30. | M20's surface is an automated session, not M30's explicit approval-bound proof. |
| `src/forex/m20_reconciliation_baseline.py` | Reconciliation source | Fails closed unless an explicit retained position identity links the assessment to complete Demo history. | Supports M30's exact broker reconciliation requirement. | It is an offline reconciliation layer and cannot create missing broker evidence. |
| `project_state.json` and current listener status observed 2026-09-16 | Runtime state | M30 is `IN_PROGRESS`; the account was flat, but the listener was held in maintenance. | Establishes the current precondition gap. | This observation becomes stale and cannot prove an eventual order. |

## Findings

### Evidence-supported

- Claim: M30 needs a separate evidence surface, not merely an M20 session
  result.
  - Evidence: M30's declared scope requires a terminal autonomous order and
    complete reconciliation; M20's capture script is scoped to its own
    continuous-session marker and contract.
  - Confidence: high.

- Claim: a fixed, Demo-only execution and reconciliation route already exists.
  - Evidence: the T480 operation is fixed to `GOMarketsMU-Demo` and `EURUSD`;
    the operation records `OPENED`, monitors, records closure, and reconciles.
  - Confidence: high for source design, not for current broker availability.

### Reasonable inferences

- Inference: binding the final persisted proposal, fixed risk limits,
  configuration fingerprint, source revision, and broker position identity in
  one evidence bundle will prevent evidence substitution.
  - Why it is reasonable: the project already uses hash-bound evidence and
    exact identity joins for provenance and reconciliation.
  - What remains unproven: the broker's later fill price, close reason, and
    costs can only be established by a fresh autonomous Demo operation.

### Assumptions to test

- Assumption: a fresh eligible proposal can be obtained while the listener is
  safely released from maintenance and still satisfies all M20 risk gates.
  - Test required: a read-only preflight observation followed by the fixed
    autonomous operation only after all existing gates are confirmed.
  - Pass/fail measure: the result is current, Demo-only, EURUSD-only, flat
    before entry, and executable; otherwise it is a refusal and no order is
    sent.

### Rejected or unsupported claims

- Claim: M30 will demonstrate profitability or future execution quality.
  - Reason: one bounded Demo trade cannot support either claim.

- Claim: M29's retained listener-recovery proof can substitute for M30.
  - Reason: M29 did not capture an approved entry, closed position, or broker
    reconciliation for M30's declared surface.

## Risks to validity

- Data quality: stale quotes, incomplete M1 bars, and broker-history delay
  must refuse the operation rather than be repaired in evidence.
- Bias / leakage: the entry decision must use only data available before the
  decision timestamp; later outcome information must remain separate.
- Execution realism: Demo spreads, fills, commissions, swaps, latency, and
  broker behaviour are descriptive only and do not generalise to Live trading.
- Generalisability: exactly one EUR/USD Demo lifecycle proves a bounded
  integration, not a strategy or a broader broker capability.
- Other risks: stale or altered approval, existing exposure, hold release,
  unresolved broker state, and a missing mandatory close must block closeout.

## Recommendation

Create ExecPlan.

## Proposed ExecPlan inputs

- Goal: produce a bounded autonomous, Demo-only M30 proof workflow.
- Scope: M30 evidence capture and verifier, exact reconciliation checks,
  tests, and formal evidence documentation.
- Non-goals: Live access, generic broker operations, trading-rule changes,
  per-order human approval, and any profitability claim.
- Acceptance criteria: M30-C1 through M30-C4 from the registry, backed by a
  fresh approved raw operation and offline verification.
- Metrics: exact persisted-proposal hash match; one position identity with an
  opened and closed history; zero unresolved reconciliation rows; evidence
  age at most 24 hours.
- Decision gate: the autonomous operation may run only while all existing
  fixed Demo safety gates allow entry; any refusal or changed input prevents
  submission.
- Evidence links: the project-contract and source paths listed above.
