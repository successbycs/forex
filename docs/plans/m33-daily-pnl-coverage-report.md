# Design a daily recorded P&L coverage report

This ExecPlan is a living document governed by `PLANS.md`. It designs a
read-only operator report that shows actual broker P&L and an explicitly
assumed commission-adjusted comparison for every recorded **closed** Demo trade
on a selected Auckland trading day. `true P&L` in this plan means the immutable
broker-recorded net P&L; the commission-adjusted amount is a labelled scenario,
not a broker charge or a Live result.

## Purpose / Big Picture

The operator can select a day with closed Demo outcomes in a read-only web
page or receive the same daily report by email at `pa@successbycs.com`. Each
report contains every closed trade, its actual broker P&L and costs, and either
a deterministically recorded commission comparison or a specific reason why
that comparison is unavailable. The report never silently omits a closed
outcome and never calculates money in the web page or email template.
PostgreSQL is the sole calculator and record keeper; every delivery channel
only displays returned facts.

The report is available on demand at any time of day. It is a snapshot of the
closed outcomes recorded when the operator requests it, not an end-of-day batch
or a scheduled email. A currently open trade remains outside realised P&L until
its broker-close outcome is recorded.

A completed report can be observed locally with a command such as:

    cd /home/chris/projects/forex
    python3 scripts/m33_daily_pnl_report.py --date 2026-09-23 --once

The expected output groups all closed Demo outcomes for that Auckland date and
shows `Actual broker P&L`, `Expected Live commission`, and `Commission-adjusted
Demo P&L` on each row. A row without safe source inputs says `UNAVAILABLE:` and
names the reason.

## Formal milestone dependency map

M32 is PROVEN and remains a reusable prerequisite. M33 is the active formal
milestone. Its currently recorded contract only covers closed, reconciled,
listener-attributed projections and a terminal ledger. The requested all-closed-
trade coverage table and selectable daily report expand that contract. They are
not authorised for runtime, schema, deployment, or proof work until Chris
explicitly approves reopening M33 and amending its registry contract.

The design wave in this plan is authorised now. The implementation wave is
blocked by that explicit governance decision. No new numerical milestone is
implied. No part of this plan authorises a broker order, Live access, MT5 change,
risk change, or mark-to-market calculation for an open position.

## Progress

- [x] 2026-09-24: documented the operator requirement for a daily report whose
  rows are calculated and retained in PostgreSQL.
- [x] 2026-09-24: inspected the existing M33 projection, audit outcome, ledger,
  fixed adapter, and terminal dashboard contracts.
- [x] 2026-09-24: Chris authorised reopening M33 for all closed-outcome
  coverage and the daily operator report.
- [x] 2026-09-24: deployed the additive coverage migration and fixed stage/apply/read adapter actions.
- [x] Added and verified the read-only terminal report, loopback web view, and non-sending email preview against the deployed selected-day coverage report. Email delivery remains intentionally unconfigured; its preview is the accepted M33 delivery-design surface.
- [ ] Collect fresh bound proof, complete independent review, and obtain a new human signoff.

## Surprises & Discoveries

- Observation: the current `forex.demo_trade_pro_forma_pnl` table has a
  non-null complete-source contract, so it deliberately cannot represent a
  partial, unreconciled, repaired-incomplete, or unattributed closed outcome.
  Evidence: `sql/migrations/026_m33_demo_pro_forma_commission.sql` requires
  volume, all broker cost fields, a canonical fingerprint, and a non-null
  calculated P&L.
- Observation: the terminal ledger defaults to the current Auckland day. It is
  unsuitable as the sole human access route for earlier trading days.
  Evidence: `scripts/m20_trade_ledger_dashboard.py` calls `render` without a
  selected day.

## Decision Log

- Decision: cover every recorded **closed outcome**, rather than every proposal,
  rejection, or open position.
  Rationale: realised P&L exists only after a closed outcome. A rejected attempt
  is not a trade and an open position needs a timestamped market valuation
  contract that this plan does not create.
  Date/Author: 2026-09-24 / Chris requirement interpreted by Codex.
- Decision: retain one immutable coverage record per closed outcome source
  revision, even when a commission comparison is unavailable.
  Rationale: the operator needs complete daily visibility without treating
  missing fields as zero.
  Date/Author: 2026-09-24 / Codex.
- Decision: use a terminal report first. A browser page may be a local,
  read-only rendering of the same fixed report data only after the terminal
  report passes proof.
  Rationale: it is the smallest observable operator interface and does not add
  web-server, authentication, or broker authority.
  Date/Author: 2026-09-24 / Codex.

## Context and Orientation

`forex.demo_trade_outcome` is the append-only record of a closed Demo trade.
`forex.demo_trade_ledger` joins it to proposal and session data for presentation.
`forex.demo_trade_pro_forma_pnl` is the existing strict M33 table: it contains
only rows with a complete, reconciled, attributed source. A pricing profile is
an immutable record of the AUD 3.00-per-standard-lot-per-side GO Plus+
assumption. A source fingerprint is a SHA-256 identifier derived from the
input facts; it prevents a later repair from rewriting a historic calculation.

The fixed PostgreSQL adapter in `scripts/postgres_pgvector_adapter.py` is the
only allowed route to the T480 PostgreSQL service. It has named, hash-bound
operations. `scripts/m20_trade_ledger_dashboard.py` is the current read-only
terminal ledger. It must remain read-only and must not gain order, risk, MT5, or
generic SQL capability.

## Proposed data contract

Add an immutable `forex.demo_trade_commission_coverage` table. Its identity is
`coverage_id`; it has a unique key of `(proposal_id, profile_version_id,
calculation_version, source_fingerprint)`. It contains:

    coverage_id, proposal_id, profile_version_id, closed_at_utc,
    actual_broker_net_aud, actual_broker_commission_aud, broker_fee_aud,
    broker_swap_aud, volume_lots, expected_round_trip_commission_aud,
    commission_adjusted_pnl_aud, coverage_status, unavailable_reason,
    source_fingerprint, calculation_version, calculated_at_utc

`coverage_status` is `APPLIED` or `UNAVAILABLE`. `APPLIED` requires all money,
volume, currency, identity and reconciliation facts and calculates each side
with PostgreSQL `ROUND(3.00 * volume_lots, 2)`. Its adjusted amount is:

    actual_broker_net_aud - actual_broker_commission_aud
      + expected_round_trip_commission_aud

`UNAVAILABLE` has null expected commission and adjusted P&L and one enum-like
reason: `NOT_MATCHED`, `UNATTRIBUTED`, `VOLUME_MISSING_OR_PARTIAL`,
`COST_COMPONENT_MISSING`, `COST_RECONCILIATION_FAILED`, `REPAIRED_SOURCE`, or
`UNSUPPORTED_CURRENCY`. The source fingerprint must identify the actual facts
and status/reason used. New source facts create a new immutable coverage row;
the daily view selects only the current source row.

The daily view returns every `demo_trade_outcome` in the requested Demo EUR/USD
scope. It left-joins the selected coverage row, so no closed outcome disappears.
It includes an Auckland local trading date derived from `closed_at_utc` and
orders rows by close time and proposal ID.

## Plan of Work

First, after explicit authorisation, amend the M33 registry and the existing
`docs/plans/demo-pro-forma-commission-design-review.md`. The new scope must say
all recorded closed Demo outcomes appear in daily coverage, with unavailable
reasons for unsafe calculations. Add acceptance criteria for complete coverage,
deterministic status selection, no null-to-zero defaulting, a selected historical
day, and continued Demo-only/no-order boundaries. Reset prior M33 closeout
records as required by the governance CLI; prior evidence remains retained but
cannot prove the expanded contract.

Second, create an additive migration, likely
`sql/migrations/028_m33_daily_commission_coverage.sql`. It creates the coverage
table, its immutability trigger, a canonical source view over every closed
outcome, and an insert-only refresh function triggered after outcome insertion.
The source view must classify every outcome before deciding whether a calculation
is allowed. It must never update broker outcomes or existing strict M33
projections. The migration must backfill each current closed outcome once and be
safe to apply repeatedly.

Third, add four named fixed adapter actions to stage/apply the migration and
read a selected Auckland date. The read action accepts only a strict `YYYY-MM-DD`
argument and must construct no caller-provided SQL. Its result includes all rows
and daily totals split into actual broker P&L, expected commission where
applied, adjusted P&L where applied, and unavailable count. It must not expose
credentials, account balances outside recorded trade rows, positions, or any
write/order operation.

Fourth, add `scripts/m33_daily_pnl_report.py`. It calls only the fixed read
operation and renders a terminal report. `--date` is required, `--once` exists
for scripts, and output has clear labels.

Fifth, implement the operator-delivery sub-plan below. The local webpage and
email must use the exact report object returned by the fixed summary operation.
They cannot issue SQL, calculate money, submit an order, or expose a control
that changes risk, accounts, or MT5.

Sixth, add unit tests for every unavailable reason, exact rounding at 0.01 and
1.00 lots, an already non-zero actual broker commission, immutable retry
behaviour, source repair creating a new coverage row, and daily view completeness.
Add an integration test that renders a day with one APPLIED and one UNAVAILABLE
row. Add browser and email-template tests using the same fixture. Run the fixed
adapter stage/apply/read evidence path on T480 only after local tests pass.

## Operator-delivery sub-plan

The operator receives two equivalent read-only views of the same daily report.
The terminal command remains the diagnostic view. A local webpage is the normal
interactive view; it shows a date picker limited to valid `YYYY-MM-DD` dates,
daily totals, each closed outcome, the actual and assumed amounts, and every
`UNAVAILABLE` reason. The page must identify the selected Auckland day,
report-generation time, PostgreSQL calculation version, pricing-profile version,
and the `ASSUMED` label. It must state that actual broker net P&L is the record
and that the commission-adjusted value is not Live broker billing.

Create `scripts/m33_daily_pnl_web.py` as a loopback-only HTTP server. It listens
on `127.0.0.1`, has one `GET /` page and one fixed `GET /report?date=YYYY-MM-DD`
endpoint, and calls `m33_daily_pnl_report.fetch_day`. It serves no write route,
no credentials, no broker controls, and no network-facing listener. The page
renders escaped text and does not embed report data in executable JavaScript.
The operator starts it locally:

    python3 scripts/m33_daily_pnl_web.py --port 8044

Then opens `http://127.0.0.1:8044/?date=2026-09-23`. The page provides a date picker and fixed `/report?date=YYYY-MM-DD` route, and shows the same rows and totals as `m33_daily_pnl_report.py --date 2026-09-23 --once`.

Email delivery is a second, non-authoritative channel. Create
`scripts/m33_daily_pnl_email.py` to render the same report as plain text and
HTML and send it only to `pa@successbycs.com`. It requires an explicit `--date`
and `--send` flag; without `--send` it writes a preview to standard output and
does not contact an email service. The mail relay hostname, port, sender, and
credential reference are operator configuration, stored outside Git. The script
must never print or retain a credential. It must use TLS, require the recipient
to equal `pa@successbycs.com`, and record a redacted delivery receipt containing
the report SHA-256, date, recipient, time, and mail-provider message ID. It must
not claim email delivery merely because rendering succeeds.

Scheduling daily email is a separate post-M33 operator decision. The initial
acceptance surface is a manually invoked send to the single approved recipient.
After a real delivery succeeds, a later plan may add a host scheduler with a
fixed selected-day policy and failure alert. No scheduler is part of this plan.
The terminal command, webpage, and email preview remain available on demand at
any time, including before a daily email would otherwise be sent.

## Concrete Steps

After authorisation, work from `/home/chris/projects/forex`.

    python3 scripts/forex_milestones.py needs-fix --id M33 --reason '<approved all-closed-trade coverage expansion>'
    python3 -m pytest -q tests/milestones/test_m33.py tests/test_postgres_pgvector_adapter.py
    python3 scripts/forex_milestones.py validate
    git diff --check

After the migration and adapter are implemented and reviewed:

    python3 scripts/postgres_pgvector_adapter.py forex-m33-stage-daily-commission-coverage-schema --approve
    python3 scripts/postgres_pgvector_adapter.py forex-m33-apply-daily-commission-coverage-schema --approve
    python3 scripts/m33_daily_pnl_report.py --date 2026-09-23 --once

The report must show every closed row for that day and must visibly distinguish
`APPLIED` from `UNAVAILABLE`. It must not submit or alter a trade. For the local
web view, start the loopback server and compare the selected day with terminal
output. For email, run preview first, inspect its rendered amounts and labels,
then use `--send` only after the operator configures a mail relay and explicitly
requests delivery.

## Validation and Acceptance

Acceptance requires a test fixture with at least one complete 0.01-lot outcome
whose `-0.06 AUD` commission produces the expected adjusted P&L; one incomplete
or partial outcome whose values are null and reason is visible; and a query
showing that both occur in the daily report. Retrying the refresh must not
create a duplicate coverage record. A source correction must retain the old row
and create a new current-source selection.

Real-world proof requires the fixed T480 stage and apply receipts, selected-day
read output, terminal report, loopback web rendering, and email preview. The
manifest binds all report, web, email, and verifier files. Governance validation,
M33 tests, independent Triad review, and a new human signoff remain required.
A real email send needs a separate operator request and its redacted receipt;
it does not permit trading as a test.

## Idempotence and Recovery

The migration is additive and insert-only. Repeating stage/apply is safe because
schema creation uses `IF NOT EXISTS` and inserts use the coverage uniqueness
key. If the apply fails, do not expose the report; inspect the fixed receipt,
correct the migration locally, and restage a new hash-bound asset. If the report
cannot read a selected day, display the source error and do not show a cached
or calculated fallback. Existing strict M33 projection and broker outcome data
remain available for comparison and are never altered.

## Artifacts and Notes

The future evidence bundle will retain the selected-day report, read result,
base and coverage migration stage/apply receipts, preflight, manifest, and
redaction statement. It must show a success marker only after every required
row/status invariant passes.

## Interfaces and Dependencies

`postgres_pgvector_adapter.py` must expose only fixed names:

    forex-m33-stage-daily-commission-coverage-schema
    forex-m33-apply-daily-commission-coverage-schema
    forex-m33-daily-commission-coverage-summary --date YYYY-MM-DD

`scripts/m33_daily_pnl_report.py` must expose:

    main() -> int
    fetch_day(nz_date: datetime.date) -> dict
    render(report: dict) -> str

`scripts/m33_daily_pnl_web.py` must expose:

    main() -> int
    render_html(report: dict) -> str

`scripts/m33_daily_pnl_email.py` must expose:

    main() -> int
    render_email(report: dict) -> tuple[str, str]
    send_email(report: dict, configuration: MailConfiguration) -> DeliveryReceipt

All three use Python standard library modules and the fixed report adapter only.
The report is a presentation layer; PostgreSQL owns all monetary rounding,
status selection, and calculation. The mail configuration is runtime-only and
must not be committed.

## Outcomes & Retrospective

M33 was reopened to `NEEDS_FIX` on 2026-09-24 after Chris authorised this
expanded contract. The additive coverage migration, selected-day terminal report, loopback webpage, and non-sending email preview are deployed or verified. Fresh bound evidence, independent review, and fresh signoff remain.

## Deferred follow-up: live execution-event logging

Chris requested a future operator-visible execution log. It is deliberately
deferred from this P&L reporting plan. The future task will add a read-only,
timestamped event stream for listener assessment, decision, submission, monitor,
and reconciliation events, with source time, proposal/attempt identity, and
safe failure detail. It must not alter listener execution, generate a second
worker, expose credentials, or make a heartbeat look like trading permission.
Its design must first establish the fixed retained event source, redaction
rules, retention period, browser access boundary, and testable stale/error
behaviour. It requires separate scope and formal-authority review before
implementation.

Revision note: created 2026-09-24 in response to Chris’s request for an
operator-visible daily report backed by deterministic PostgreSQL calculations.
Revision note: expanded 2026-09-24 to include a loopback read-only webpage and
an explicit-send email design for pa@successbycs.com; no delivery configuration
or email was created.
Revision note: M33 contract amended and implementation authorised on 2026-09-24
for all recorded closed-outcome coverage and the operator delivery surfaces.
Revision note: clarified 2026-09-24 that every operator view is on-demand and
available at any time of day; no end-of-day batch is required.
Revision note: added 2026-09-24 deferred execution-event logging follow-up at
Chris's request; it is not part of the M33 P&L-report delivery scope.

Revision note: Astra review on 2026-09-24 found M33 source-change coverage could go stale and the initial 029 staging operation omitted the fixed local-to-T480 SCP transfer. Migration 029 adds idempotent refresh triggers for outcome, execution-attempt, position-event, and reconciliation-revision changes. Its staging action now follows the existing hash-bound SCP, source-hash, copy, and destination-hash pattern; it was successfully staged and applied on T480.


## Broker P&L ledger expansion

Chris clarified on 2026-09-24 that the operator needs the entire broker account
ledger, rather than only listener-attributed outcomes. Add the immutable
`forex.demo_trade_pnl` table, shown as **P&L** in operator reports. Its stable
identity is the MT5 deal ticket and it records broker time, receipt time,
side, entry/close event, volume, price, commission, fee, swap, realised trade
P&L, net movement, balance before, balance after, source-history digest and
collection version. The table is insert-only; a corrected broker observation is
a new revision linked to the original ticket, never an overwrite.

A fixed, read-only MT5 history collector retains raw broker response first and
then writes validated deal facts through a fixed PostgreSQL operation. It runs
on the existing post-trade collection path and reconciles every retained deal,
including `DEAL_TYPE_BALANCE` movements, before publishing a daily P&L report.
The daily view groups the Auckland day and returns opening balance, every deal,
trade P&L, broker costs, net movement, and closing balance. A missing anchor or
unreconciled broker history is `UNAVAILABLE`; no balance is inferred as zero.

Acceptance proof must reproduce the 2026-09-23 MT5 bridge: opening AUD
100,989.45, all 30 broker deals, net AUD -30.50, and closing AUD 100,958.95.
It must separately identify the 11 listener-attributed M33 outcomes and the
four earlier 0.02-lot close deals whose AUD -28.64 loss was not in that view.
No collection or ledger action may submit, modify, or close an order.


## Astra journal repair — 24 September 2026

Review found the initial journal deployment unproven and its balance anchoring
unsafe: the post-execution capture reused the pre-execution balance. Individual
deal deduplication also prevented corrected running balances and reversion to
previous deal values. The report mixed account scopes, rounded money in Python,
and added assumed commission on top of actual commission.

The repair uses additive migration 031, leaving raw receipts unchanged. Each
validated full capture projects its entire ledger with PostgreSQL numeric
arithmetic. Total retained broker movements must match the observed balance.
Raw text commits before projection so failures remain inspectable. Two identical
history reads bracketed by equal fresh balances are required. Full MT5 objects
and millisecond timestamps are preserved. The report refuses ambiguous accounts
or an unreconciled latest receipt, shows local Auckland times, and separates
all-history trading P&L from balance funding movements.

Run the fixed stage/apply broker-pnl-journal-repair-schema operations, then
stage and run broker-pnl-journal-verify; synthetic assertions roll back. Stage
all hash-bound listener payloads, prepare and configure the release, then use
`m33_broker_pnl_collect` to capture real history without starting the listener
or entering an order path. Query 23 September and compare all 30 rows, opening
100989.45, movement -30.50, closing 100958.95. Re-run collection and confirm
unchanged economic totals. Render the same PostgreSQL receipt in CLI and web.

Startup diagnosis found the task Disabled with Interactive logon, no explorer
sessions, and no fresh failure records. A missing interactive desktop is a
separate operational prerequisite; configuration repair alone did not restore
it. Do not claim rolling collection until the listener runs in its required
interactive desktop and a subsequent capture proves it. No automatic fallback
to a Session-0 trading worker is authorised by this repair.

Owned repair paths: journal bridge, runner, listener service, fixed T480 and
PostgreSQL adapters/catalog, migration 031, journal summary/verification SQL,
operator report/web, focused tests, and this plan/work record. Existing raw
observations and unrelated milestone proof remain unchanged.

<!-- forex-work-projection:start task=M33-JOURNAL-REPAIR schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=review state=DONE -->
- [x] review — Review accounting defects and failed listener startup (DONE)
<!-- forex-work-item id=repair state=DONE -->
- [x] repair — Repair projection, stable collection and operator report (DONE)
<!-- forex-work-item id=database-proof state=DONE -->
- [x] database-proof — Apply repair and run rollback-only PostgreSQL regressions (DONE)
<!-- forex-work-item id=broker-proof state=DONE -->
- [x] broker-proof — Stage prepared collector and verify actual 23 September report (DONE)
<!-- forex-work-item id=rolling-proof state=BLOCKED -->
- [ ] rolling-proof — Verify automatic collection on an active listener (BLOCKED)
<!-- forex-work-projection:end -->

Revision note: Astra review corrected accounting, provenance and startup assumptions; operational acceptance remains pending as indicated above.

Revision note: final Astra review added post-monitor/recovery collection even
while entries are held, with an acknowledged-receipt cache. Any economic
change is collected immediately; unchanged history refreshes hourly or at the
Auckland day boundary, and explicit collection always refreshes. The cache is
invalidated before each fresh bridge attempt so failed projections cannot
suppress retries. Missing timezone data fails explicitly. The 1 MiB bridge
request envelope is an additional bound below the 10,000-deal count ceiling;
current 175-deal history fits. Funding-day reports now separate trading P&L
from deposits. 189 affected tests passed before the final cache retry fix;
15 focused cache/report tests passed afterward. PostgreSQL rollback regression
passed on the real T480 database; initial payload staging was stopped before
installation to include these review fixes.


### Verified result and remaining operational blocker

The fixed deployed collector for release `e786bc9636f756ce`, committed code
`12eaaa4`, inserted all 175 actual broker deals. Repeat collection retained
30 current September23 line items without changing balances or totals. All
nine retained activity dates reconciled independently, including the funding
day. September24 has no new trades and correctly shows zero daily P&L with
opening/closing AUD100958.95. The real HTTP operator page returned200 with
30 September23 transaction rows; terminal output agrees.

September23: opening100989.45, actual net movement/trading P&L-30.50,
closing100958.95, assumed expected commission-1.14, adjusted P&L-31.64.
All retained trading days: actual P&L-41.05, adjusted P&L-46.51. Funding is
excluded from trading totals. Amounts are AUD; expected commission is an
assumption, not an observed broker charge.

Open `http://127.0.0.1:8044/report?date=2026-09-23` on this host, or run
`python3 scripts/m33_daily_pnl_report.py --date 2026-09-23 --once`. The
loopback web process is running for operator access; reboot persistence is
not asserted by this repair. Explicit collection is
`python3 scripts/t480_adapter.py execute --operation m33_broker_pnl_collect`.

Raw deployment, collector, PostgreSQL and HTTP evidence is retained under
`runs/local/m33-journal-repair-20260924-v2`, with file hashes in
`checksums.json`. The first configure attempt correctly refused an absent
prepared binding; preparing before configuring resolved that precondition.
The earlier directory retains the original diagnostics, SQL rollback proof,
and the interrupted pre-review payload transfer. These are implementation
acceptance records, not human signoff or formal milestone closure.

Astra found no remaining blocker in its bounded final collector/cache review.
The189-test combined affected suite passed before the final cache retry
fix; later focused tests covered cache/timezone/recovery changes; final targeted collector suite11 passed,
report suite5 passed, and M33 evidence/milestone compatibility suite11 passed.
SQL regression ran against PostgreSQL and rolled back its synthetic data.
Governance and diff checks passed. Final continuation remains blocked only
on Windows desktop availability and subsequent listener activation/runtime
proof; the task remains disabled. The operator was asked to sign in as OEM.
No order was submitted and no formal milestone state was advanced.
