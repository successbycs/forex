# Evidence Brief: M31 Demo outcome evaluation baseline

## Decision

Decide the smallest reproducible way to evaluate the protected EURUSD Demo M1
workflow after M30 without changing a strategy, risk limit, account, or broker
route.

## Proposed claim or hypothesis

For a pre-declared observation interval, the retained M1 decision and broker
outcome records can be compared with a frozen historical reference without
look-ahead or a claim that the strategy is profitable. A valid outcome may show
too little data, unavailable costs, or no improvement over the reference.

## Context

- Instrument / market: EURUSD on `GOMarketsMU-Demo` only.
- Timeframes: completed M1 decisions; M5/H1 remain recorded shadow context.
- Data source: immutable listener assessment records, broker reconciliation,
  and existing PostgreSQL audit facts captured by fixed read-only operations.
- Period examined: a M31 pre-declared forward window, fixed before evaluating
  outcomes; no minimum return, trade count, or income target is assumed.
- Intended use: research evaluation and an operator-readable scorecard.
- Known constraints: M30 evidence is one lifecycle, commission and financing
  are not qualified for this Demo account, and historical M16 H1 data cannot
  be numerically substituted for the M1 strategy workflow.

## Evidence reviewed

| Source | Type | Relevant finding | Applicability | Limitations |
| --- | --- | --- | --- | --- |
| `milestone_registry.json` M31 contract | Governing primary record | M31 requires controlled Demo outcome evaluation against pre-declared historical baselines, provenance, and no Live access. | Defines scope and proof. | Does not prescribe a metric or data window. |
| `docs/milestones/M20.11-five-strategy-demo-trial.md` | Current workflow contract | One strategy owner and one EURUSD position make results attributable. | Supports per-strategy counts and outcomes. | It deliberately excluded a historical baseline before enablement. |
| `docs/milestones/M16-proof.md` | Retained historical-evaluation proof | M16 used frozen chronological windows and a `NO_CHANGE` baseline with explicit cost sensitivity. | Supplies a safe methodological pattern. | H1 historical data and its retrospective availability policy are not an M1 strategy benchmark. |
| M30 bundle `runs/evidence/M30/natural-raw-20260922T215346442193Z` | Current system evidence | Captures a Demo-only protected and reconciled lifecycle with revision/configuration identity. | Proves the evaluation input lineage begins from an operating workflow. | One lifecycle is not performance evidence. |
| `docs/reviews/hybrid-milestone-alignment-review-2026-09-17.md` | Scope review | M31 evaluates accumulated forward outcomes; it must retain signal counts, selections, refusal reasons, costs, outcomes, and uncertainty. | Defines a minimal scorecard. | It is a recommendation, not a measured result. |

## Findings

### Evidence-supported

- M31 is an evaluation milestone, not authority to add strategy logic or Live
  access. Confidence: high.
- Every selected Demo outcome can be attributable to a candle-keyed decision,
  strategy owner, configuration identity, broker reconciliation, and observed
  cost fields where present. Confidence: high for fields retained by the M30
  workflow; coverage must be measured for the actual M31 interval.
- `NO_TRADE` is a valid normal decision and belongs in denominator counts.
  Confidence: high.

### Reasonable inferences

- The smallest valid baseline is a frozen `NO_CHANGE`/no-exposure reference:
  zero trades, zero realised P&L, and zero costs. It lets the scorecard state
  whether the Demo workflow took risk and what it realised, but it cannot show
  a trading edge by itself.
- A historical comparator is useful only when it has the same M1 decision
  rules, point-in-time inputs, execution-cost assumptions, and declared window
  logic. Otherwise it must be labelled `NON_COMPARABLE_CONTEXT`, not converted
  into a numerical profit comparison.

### Assumptions to test

- Existing fixed read-only sources can export a complete bounded M31 interval
  containing decisions, proposals, attempts, reconciliations, and outcomes.
  Pass: every source response has a declared interval, digest, and joins are
  complete or explicitly classified. Fail: absent, stale, ambiguous, or
  incomplete records block the affected comparison.
- Broker-reported commission, swap, fee, spread, and slippage coverage is
  sufficient for a net-outcome column. Pass: each trade is fully covered or
  labelled with the exact unavailable fields. Fail: no estimated Live cost or
  profitability statement is produced.

### Rejected or unsupported claims

- A single M30 trade proves a profitable strategy: rejected.
- M16 H1 historical results are a direct numerical baseline for M1 Demo
  strategies: rejected.
- An incomplete cost record can be filled with a broker website tariff or an
  assumed commission: rejected.

## Risks to validity

- Selection bias: do not choose the interval after viewing a favourable result.
- Look-ahead: a row may use only data available at its decision time.
- Execution realism: use broker-reported values when present; preserve missing
  values as unknown.
- Generalisability: M31 reports observed Demo results, not expected returns or
  Live performance.

## Recommendation

Create and execute a bounded M31 ExecPlan. First freeze the interval, baseline,
metrics, cost-coverage labels, and no-promotion rule in a versioned protocol.
Then collect only fixed read-only evidence and build a deterministic scorecard.
Do not start an evaluation interval until its protocol hash is retained.

## Proposed ExecPlan inputs

- Goal: controlled, reproducible Demo outcome evaluation against a frozen
  no-exposure baseline and any qualified like-for-like historical comparator.
- Scope: existing M1 audit/reconciliation facts and fixed read-only captures.
- Non-goals: strategy changes, account changes, Live access, cost assumptions,
  automatic promotion, and broader ledger/schema work.
- Acceptance: an operator can see interval coverage, decision/refusal counts,
  selected-trade outcomes, cost completeness, baseline comparison, uncertainty,
  and raw evidence references.
- Decision gate: human review of the frozen protocol precedes capture; a missing
  like-for-like historical comparator yields an honest contextual result rather
  than a replacement benchmark.
