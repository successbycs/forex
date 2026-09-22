# Listener operator workflow view

Design reviewed on 2026-09-22 in response to Chris's request for a terminal
workflow from candle price through assessment and trade, reusable later on web
and Discord. Implemented locally through docs/plans/listener-workflow-view.md.
Run `python3 scripts/m20_listener_dashboard.py`; use `--once` for a snapshot,
`--width 60` for a narrow view, or `--json` for the reusable report object.

## Review of the existing views

The established command remains `python3 scripts/m20_listener_dashboard.py`.
It already shows candle checks, five strategies, the selected owner, costs,
execution, reconciliation and M5/H1 context. It was not replaced in the
repository; recent instructions mistakenly directed the operator to raw adapter
JSON. A subsequently created short helper was removed. Do not introduce another
competing terminal entry point.

Reuse `scripts/m20_trade_ledger_dashboard.py` for lifecycle and verified outcome
semantics, and `scripts/m20_listener_evidence_view.py` for exact proposal joins.
The raw adapter response remains a diagnostic/evidence interface.

## Operator layout

Keep a stable summary at the top, followed by numbered workflow stages. Put
active exposure and operational faults above the details so they remain visible
in a small terminal. All existing full-dashboard details remain available below
the summary. Use plain text labels as well as any optional colour. Wrap to the
terminal width; use stacked rows for narrow terminals. Display Auckland local
time with its actual timezone abbreviation and retain UTC in detail output.

Illustrative layout only; values below are placeholders, not live observations:

```text
EUR/USD DEMO | Listener: <state> | Updated: <time and age>
Positions: <broker observation or UNKNOWN> | Attention: <reason or none>

1 PRICE & CANDLE
  Quote: bid <price> / ask <price> | spread <points> | quote age <age>
  Closed M1 candle: <time> | close <price> | previous close <price>
  Forming candle: <available OHLC or NOT AVAILABLE>

2 ASSESSMENT
  Momentum       <signal>  <reason>
  Compression    <signal>  <reason>
  Trend pullback <signal>  <reason>
  Range reversion<signal>  <reason>
  Session        <signal>  <reason>
  Selected owner: <strategy or none> | Regime: <state and reason>

3 DECISION & CHECKS
  Decision: <BUY / SELL / NO TRADE / unavailable> | Why: <reason>
  Risk: <recorded permission/pause or UNKNOWN> | Costs: <recorded result>
  Plan: entry <price> | size <lots> | stop <price> | target <price>

4 EXECUTION & PROTECTION
  This decision: <not submitted / accepted / rejected / unknown>
  Active trade: <separate exact attempt/ticket or unavailable>
  Protection: <current observation and time, or last-known/unverified>

5 CLOSE & RECONCILIATION
  Recent trades: <time, strategy, side, entry, exit, reason, verified net AUD>
  Outcome: <open / closed awaiting reconciliation / closed verified / error>

DETAILS: candle checks | M5/H1 context | identifiers | source freshness
```

`NO_TRADE` ends that candle's decision path normally. It does not mean the
listener has stopped or the account has no open positions. An earlier trade
continues through its own monitoring and close stages while later candles are
assessed. Do not present one global progress bar as if all panels belong to the
same trade. Each decision and trade carries its own identity and timestamps.

## Evidence and display rules

| Panel | Existing source | Missing or ambiguous facts |
| --- | --- | --- |
| Health and cadence | Fixed listener status | UNAVAILABLE or STALE with last observed time |
| Quote and candle | Status quote and assessment metrics; retained assessment | Missing bid/ask remains unavailable; never relabel last candle close as current price |
| Five strategies and owner | Recorded strategy assessments and selection | Show unavailable reasons without calculating new signals |
| Risk and cost checks | Retained assessment risk policy and strategy selection | UNKNOWN when omitted; a running heartbeat does not prove permission |
| Order and protection | Exact execution attempt and monitor observation | Retained protection record is explicitly last-known/unverified |
| Current exposure | Fixed deployed-account identity observation | Failed account query never means zero positions |
| Close and P&L | Fixed PostgreSQL lifecycle summary and reconciliation | No per-trade profit inferred from account balance change |

Latest status often omits the live quote and full risk policy. The initial
implementation must show these gaps explicitly. Use the existing retained
assessment export for additional recorded fields, joined by exact proposal id;
if it has advanced to a different decision, show the mismatch rather than
combining fields. Current status does not supply a forming candle's full OHLC:
display NOT AVAILABLE until an authorised existing source supplies it. Strategy
assessment uses closed candles; a forming candle is context only.

Show independent fetch/capture times for status, assessment, account and ledger.
The implementation replaces failed reads with UNKNOWN rather than caching old
values. A stale heartbeat is prominently labelled with age. Historical rows remain historical even when their fetch is
fresh. Use UNKNOWN for absent evidence, N/A for genuinely inapplicable fields,
and a reason for a blocked or rejected transition. Do not turn duplicate
assessment persistence into another order notification.

## Reuse across terminal, web and Discord

Keep read-only collection, report construction and rendering separate. A plain
Python report object should carry observation times, source availability,
instrument, stage labels, reasons, and decision/attempt/ticket identities. Build
it from the existing fixed operations and ledger query. The terminal renderer
formats that report; a future web renderer can use the same report as cards,
and a future Discord renderer can summarise meaningful state changes keyed by
event identity. Display code must not recompute trading rules.

No web server, Discord integration or new transport is needed for this design.
The stable dashboard command remains the operator entry point. Keep full detail
as the default; a future compact mode may be optional, never a silent replacement.

## Implementation acceptance

Enhance the existing dashboard and reuse the existing ledger and evidence
readers. Validate a NO_TRADE decision, an accepted protected trade, a verified
close, a rejection and unavailable/stale sources. In particular, test a newer
NO_TRADE alongside an older open trade, mismatched proposal ids, and retained
protection after closure. The display must not invent risk permission, current
protection, exposure or profit. Verify one actual read-only terminal rendering
at normal and narrow widths. Existing dashboard, ledger and evidence-view
checks must continue to pass. Record implementation results separately from
this design review. Only local presentation code changes are required.
