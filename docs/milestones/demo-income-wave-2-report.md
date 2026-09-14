# Wave 2: costs, data and executable-research handover

## 2026-09-12 retained D1 inventory correction

`runs/evidence/M6/current/probe.json` also retains 365 D1 bars, not only
the previously discussed H1 sample. Inspection decoded its gzip/base64 payload
and matched the declared decoded-byte SHA-256
`0a4caad91b3757747dc30d2501a846309250873b185c84061b62491f374cd8f3`.
The D1 opening-date range is 2025-04-03 through 2026-08-28. Reuse this retained
source where suitable rather than assuming an entirely new year-long download
is needed. This is inventory/integrity evidence, not H_SLOW dataset approval:
the September target still needs the final August session, the required
month-end coverage checks and explicit historical-availability treatment.

## 2026-09-12 retained M20 replay inventory

`scripts/m20_replay_batch_report.py runs/evidence/M20` is a read-only,
hash-bound inventory over direct retained `demo-trading-operation.json`
sources. It never repairs a source, follows no symlinked run directory, caps
source size/count, and intentionally does not sum money across independently
unreconciled source files. Unsupported or malformed captures retain both their
path, raw SHA-256 and refusal reason.

The current retained set has 20 source files: 16 reportable operation exports
containing 16 replayable pairs, of which nine classify successfully and seven
are retained as older-schema classification errors. Four sources are refused
because their fixed T480 `stdout` value is not JSON; their raw source digests
remain in the report. No reportable source contains a linked broker outcome,
so broker-outcome count is zero and the aggregate financial conclusion is
`NOT_EVALUATED_SOURCE_LEVEL_DUPLICATES_AND_OUTCOMES_NOT_RECONCILED`.

This is an inventory of the imported Demo records, not a repair of the seven
older schemas or four malformed captures, a profitability finding, broker
provenance proof, or a reason to infer zero costs. Future loss-accounted spool
captures will enter this review path only after their immutable local retention
and the relevant source/provenance checks.

## 2026-09-12 retained MT5 history summary

`scripts/m20_history_report.py` is a separate strict reader for the fixed
`m20_wave1_history` Demo envelope. It accepts only GOMarketsMU-Demo EURUSD
deals under the M20 magic ID, preserves incomplete positions rather than
inventing closes, and keeps commission, fee and swap distinct from price P&L.
It is read-only and hashes the raw outer source.

The earlier closeout source
`runs/evidence/M20/w1-closeout-20260910T084421Z/raw/history.json`
(`sha256:73e878bdc2ca93392b55ff64997d9f198aedf4bdfbedef8189c7af7421c806bf`)
contains 31 deals across 16 positions. Fifteen positions are paired closed:
11 losses, two wins and two flats, for AUD **-3.19** realised net price-plus-
reported-charge P&L; eight closes are stop-loss-like. Position `42235606` has
an entry but no exit in that particular capture.

A later retained fixed-history capture,
`runs/evidence/M20/w1-supervised-restart-20260910/raw/broker-history.json`
at 09:29:55Z (`sha256:70f9d7be3f718b07f7393e25869dc08530ddb9d5dbbf4cc38fafbbcb471481a8`),
contains 38 deals and 19 paired closed positions: 15 losses, two wins and two
flats, for AUD **-4.10** net; eight closes are stop-loss-like. Thus the later
source adds four closed losses totalling AUD -0.91 after the earlier closeout
capture. Reported commission, fee and swap fields total AUD 0.00 each in both
fixed-history captures.

This is a bounded historical observation, not a current account state, a
strategy-economics conclusion, a full charge/tariff assertion, or a link to a
specific retained decision/proposal. It confirms a negative outcome across the
latest retained history capture and should inform a later bounded review, not
trigger automatic retuning, loss-chasing, risk expansion or data repair.

### Fresh read-only all-history observation — not a formal retained bundle

At 2026-09-12T04:55:45Z the fixed read-only
`m20_all_demo_history_export` operation observed 123 account deal rows. After
excluding three non-M20/EURUSD Demo deposit rows, its exact M20 EURUSD scope
contained 120 deals / 60 paired closed positions: 45 losses, 11 wins, four
flats, AUD **-10.41** net, and 16 stop-loss-like exits. Reported commission,
fee and swap remained AUD 0.00. The all-history reporter accepts this named
schema only and rejects non-finite values; it does not treat deposits as trade
results.

The exact adapter response is now immutably retained under ignored local
operator storage at
`runs/local/m20-history-captures/m20-all-history-d66933f404af3574/`, alongside
its hash-bound report and receipt. This is operational retained evidence, not
a formal M29 proof bundle. It confirms that the later imported capture
understated the subsequent negative sequence; it does not establish strategy
causation, complete costs, current availability, M29 proof or authority to
automatically change the M1 policy, limits or risk-resume state.

## 2026-09-11 contract and implementation audit

**Status: IN PROGRESS — contract mapping complete; no execution behaviour,
configuration, retained market-data surface, or T480 release has changed.**

Wave 1's amended core scope is complete. The M20 listener remains the only
execution writer and continues under its existing Demo-only authority. Final
M20 and W4.1 evidence remains deferred as recorded in the Wave 1 handover.

### Current evidence and capability inventory

| Wave 2 item | Current evidence/capability | Gap and disposition |
| --- | --- | --- |
| Actual broker net and fee completeness | `demo_trade_ledger` retains gross price P&L, commission, fee, swap, estimated costs and fee-completeness exclusions. Retained historical Demo rows contain attributable zero-charge closes. `forex-m20-audit-verify` currently passes `fee_incomplete_excluded=true`. | Actual nonzero charge, 20-consecutive-close accounting checkpoint, and separately posted-charge allocation are observations, not a reason to invent data. Continue ordinary collection; do not make an economics claim. |
| Temporary entry economics | The effective M20 mandate has a labelled AUD 6/lot `DEMO_ESTIMATE`, current 06:00–18:00 UTC intraday boundary, fresh conversion observation, and a cost-coverage refusal. | It is not account-tariff, rollover, holiday, or nonzero-cost qualification. Any replacement with account-qualified terms changes execution policy and needs the amendment below. |
| Pre-submit checks | Existing execution validates Demo server, quote/M1 freshness, account/risk state, one-position/reservation, volume/stops, broker result context, and persists an auditable no-submission outcome when prerequisites expire. | A new final `order_check`, margin, freeze-distance, deviation, event-window, or delayed-audit revalidation gate would change M20 order semantics and requires amendment before deployment. |
| Pure research contracts | `src/forex/data_contracts.py` already enforces UTC availability and source provenance. `src/forex/replay.py` supplies cutoff alignment. `src/forex/demo_trading.py` is broker-independent but implements an older M1/M5 policy, not the deployed five-owner M1 policy. | Build a new pure kernel that represents the deployed policy without importing MT5, PostgreSQL, environment, or order APIs. It must initially consume retained decision snapshots only. |
| Point-in-time replay | M13's historical alignment is proven under its stated retrospective assumptions. M20 retains decision snapshots, proposals, execution attempts and outcomes suitable for comparing a pure kernel with already-captured decisions. | The existing 720 H1-bar history and historical availability assumption are insufficient for slower-candidate research. Additional source-backed datasets or quote retention require amendment and separate qualification. |
| Event eligibility and financing history | Existing M20.14 context is shadow-only. Current financing mandate is intraday-only and refuses unsupported terms. | A complete event source, blackout influence, historical swap calendar/rates, conversion series, or overnight counterfactual requires qualified sources and an amendment. No event or hold rule may influence execution in Wave 2. |

### Contract mapping

The following is safe to implement and test now because it is offline,
read-only and cannot affect the listener:

1. A pure versioned representation of the **currently deployed** M1 policy,
   including five strategy assessments, deterministic owner selection, fixed
   plan validation, cost-result classification, protection/owner exit
   instruction, and explicit `NO_TRADE`/`UNKNOWN` outcomes.
2. A replay adapter that accepts only retained decision snapshots and lifecycle
   inputs, requires explicit `closed_at_utc` and `available_at_utc`, and
   exposes ambiguous stop/target ordering as `INDETERMINATE`.
3. A cost-accounting report that separates actual broker net P&L from estimated
   execution costs, preserves missing values, and reports coverage rather than
   treating missing values as zero.
4. Tests comparing the pure kernel's output with retained deployed decision
   records. This is parity evidence, not strategy validation or permission to
   change execution.

The following require an approved M20 contract amendment **before dependent
implementation or deployment**:

1. Any live entry influence from event calendars, a changed session gate,
   additional final order revalidation, modified sizing/stops/deviation, margin
   gate, or changed financing/holding rule.
2. Retention of ticks, bid/ask samples beyond existing decision records, new
   broker observations, external event feeds, swap histories, conversion
   histories, or a source-backed slower dataset.
3. Running a replay-derived policy, counterfactual hold result, or a new cost
   assumption in the T480 execution path.

### Proposed M20 amendment — review only, not applied

Add a **Wave 2 research-only extension** to M20 scope:

> Permit a local, non-executing, versioned pure policy kernel and replay/report
> path that consumes only retained M20 decision snapshots, proposal/attempt/
> outcome records and already-approved historical artifacts. It may produce
> `BUY`, `SELL`, `NO_TRADE`, `UNKNOWN`, or `INDETERMINATE` research results but
> has no MT5 import, order, listener, scheduler, broker-write, lease-write,
> configuration-write, or live-data-retention capability. Every input declares
> `closed_at_utc`, `available_at_utc`, source/revision and cost-status. Unknown
> fill order, fee, financing, conversion or source availability remains unknown
> or indeterminate. It must not alter the deployed M20 strategy, risk, entry,
> exit, session, cost gate, or protected-position behaviour.

Add the following explicit exclusions:

> No additional tick stream, quote archive, external event feed, historical
> swap/conversion collection, execution-time event/margin/order-check gate,
> changed financing mandate, or replay-selected strategy may be introduced
> without a separate approved amendment that declares source, licence,
> retention, availability, revision, execution impact and affected proof.

The amendment supports W2.2's offline parity work only. It does not authorise
W2.1's live-policy changes, M21/M26/M28 execution, Wave 3 research selection,
Live access, or M20 closeout.

### Next implementation slice

Implement the pure current-policy kernel and retained-snapshot
characterization adapter first, offline and under the present M20 scope. Its
integration with a deployed execution release requires affected M20 proof to be
revalidated. Expanded datasets, quote retention, independent account-path
replay, event collection, or any execution influence require separate,
specifically scoped M20 amendments; the proposed research-only extension
expressly excludes them. Then use ordinary natural Demo collection for the
20-close cost checkpoint; do not poll or trade to fill the sample.

### Current blockers and resumption condition

The retained-evidence characterization and a pure current-policy kernel can
proceed offline under current M20 scope. Its integration/release requires
affected M20 proof revalidation. Expanded datasets, quotes, event collection,
independent account-path replay, or any execution influence require separate,
specifically scoped M20 amendments; they are excluded from the proposed
research-only extension. All execution-influencing, external-data, and
additional-retention W2 items remain separately blocked by their own proposed
amendments and qualified sources. The running Demo listener remains unchanged.

## 2026-09-11 first offline implementation slice

`src/forex/m20_policy_kernel.py` is a versioned pure representation of the
currently deployed M20.11 five-owner M1 assessment, deterministic regime
precedence, owner-specific protected trade plan, Option B loss calculation, and
owner time/invalidation exit instruction. It has no MT5, PostgreSQL,
environment, filesystem, network, listener, scheduler, or order dependency.
It returns no execution authority.

The retained-snapshot classifier requires explicit closed M1 intervals and
rejects gaps, future bars, malformed OHLC, and future availability. Existing
M20 snapshots that lack `available_at_utc` may be characterized against their
recorded closed candles, but are labelled `UNQUALIFIED_AVAILABILITY`; no
point-in-time performance conclusion is made from them. Even a record with
consistent clocks and gates remains `PROVENANCE_UNVERIFIED` until a separately
qualified source/provenance contract exists. Adding an authoritative
availability clock to future retained records needs the proposed M20 amendment.

Local parity tests compare the pure strategy assessments, regime precedence,
and each owner's protected plan with the currently deployed T480 source. The
focused regression suite and milestone governance validation passed on
2026-09-11. This is source-level parity evidence only; the kernel is not
integrated with or deployed to the listener, and it neither changes the current
Demo strategy nor authorises orders.

### Astra affected-area review

On 2026-09-11, Astra accepted this offline first slice after read-only review.
The review confirmed formula, precedence, stop rounding, loss calculation and
owner-exit parity with the deployed source, plus explicit refusal of incomplete
clocks/gates and unverified provenance. The acceptance is limited to
source-level characterization; it does not qualify replay data, approve
integration or deployment, or complete Wave 2 or M20.

## 2026-09-11 broker-cost accounting slice

`src/forex/m20_cost_accounting.py` adds an offline M20 outcome classifier. For
each already matched AUD broker outcome, it separately retains gross price P&L,
actual commission/fee/swap, estimated spread/slippage figures, and realised
broker P&L. It checks the broker arithmetic only when all actual cost fields
are present; absent values remain `INCOMPLETE`/`UNKNOWN`, never zero. Estimated
execution costs are reported separately and are never subtracted from broker
realised P&L a second time. The aggregate reports evidence coverage only and
always returns `NOT_EVALUATED` for profitability and no execution authority.

This is not connected to a database query, listener, broker operation, or
release. Read-only processing of already retained M20 outcomes remains within
this slice. Additional collection, changed retention, execution influence, or a
fee-gate change require separately scoped M20 approval and affected-proof
revalidation. The AUD 0.005 amount-level arithmetic tolerance is only a
rounding consistency check; it is not a 20-close acceptance policy.

### Astra affected-area review — broker-cost accounting

On 2026-09-11, Astra accepted the offline accounting slice after read-only
review. Acceptance covers amount-level consistency only: it is not independent
proof of broker provenance, charge completeness, profitability, deployment, or
milestone completion.

## 2026-09-12 reusable annotation and slower-policy input slice

**Status: REVIEWED, research-only.** This slice adds no publisher collection,
broker call, retention surface, execution-time filter, account selection or
order authority.

| Component | Implemented boundary | Verification and limitation |
| --- | --- | --- |
| `forex.event_quality` + `forex.event_annotations` | A decision-time event result retains source, revision, availability, schedule and quarantines. The annotation output is `EVENT_CONTEXT_ONLY`, with coverage explicitly `UNKNOWN`; it has no allow/block/direction field. | Focused event and M21 controls reject unavailable, cancelled, superseded, date-only and invalid-DST source records. This does not qualify a complete publisher feed or a healthy-calendar claim. |
| `forex.h_slow_data` | Converts only an already-valid EUR/USD `D1` dataset snapshot at the exact decision cutoff into completed, available UTC daily bars, bound to the snapshot artifact hash. | Rejects wrong scope, non-midnight D1 timing, pre-close/future availability, stale cutoff and malformed snapshots. It is a read-only adapter, not a new data source or retention authority. |
| `forex.h_slow_decision` | Binds the validated slower-policy input and target to a deterministic research record. A digest-verified matching event annotation may be attached for review only. | The attached context cannot modify the target or grant execution authority; mutation isolation is covered. A `BUY`/`SELL` result remains `RESEARCH_TARGET_ONLY`, not an order instruction. |

The slower stream's account/terminal, risk limits, sizing, broker protection,
financing, holding/reversal and reconciliation are deliberately not inferred
from these components. Their exact human-owned fields are retained in
[`H_SLOW Demo activation contract draft`](../../Research/experiments/h_slow_eurusd_tsmom_12m_v1/demo-activation-contract-draft.md).
The separate D1 input requires a qualified snapshot before use; the existing
M2 H1 retained data is not silently re-labelled as slower-strategy data.

Focused regression commands passed locally:

```text
python3 -m pytest -q tests/test_event_annotations.py tests/milestones/test_m21.py
python3 -m pytest -q tests/test_h_slow_data.py tests/test_h_slow_decision.py tests/test_h_slow_policy.py
python3 -m pytest -q
python3 scripts/forex_milestones.py validate
```

These results are implementation evidence only. They do not constitute a
qualified dataset, cost observation, execution demonstration, profitability
result, M20/M29 proof, or activation authority.
