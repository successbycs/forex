# Forex economic-event layer: solo-operator review

Sequencing update, 2026-09-12: the [shared wave guide](../prompts/demo-income-waves.md)
and [Wave 3](../prompts/demo-income-wave-3.md) now specify initial event
annotation alongside M1 and a longer-hold Demo stream. Entry-filter proposals
below are deferred refinements, not default trading gates. Coverage quality
and timestamp requirements remain relevant to honest annotations and any
later explicitly activated filter.

Review date: 2026-09-12. Scope: architecture guidance and a bounded proposed
implementation package, following Chris's request to focus on Forex while
market-dependent execution proof is parked. This document does not start a
future numbered milestone or change trading policy.

## Recommendation

Build one reusable Python event module inside the Forex repository initially.
Give it an asset-neutral schema and no dependency on MT5, strategies, accounts
or orders. Forex owns the EUR/USD relevance mapping and event-window policy.
Use the existing PostgreSQL service and an existing scheduler integration after
deployment qualification. A separate repository/API service is unnecessary for
one consumer; extract the module when a second application actually needs it.

This revises the earlier preference for an immediate sibling research engine.
One operator benefits more from fewer deployments and a small maintained source
set than from speculative platform infrastructure. Shared infrastructure remains
owned by cs-ai-lab-infra; application event semantics belong to Forex.

The first business question is whether trustworthy event context helps the
existing EUR/USD policy avoid poor entries or explains its outcomes. Return
improvement is an empirical question. More events, trades or model calls are
not measures of economic success.

## Findings from current source

- `src/forex/calendar_events.py` fetches a 20-record FRED CPI release-date sample
  and up to 20 parsed ECB statistical calendar entries. These samples do not
  establish upcoming EUR/USD event coverage. Event identity incorporating a
  schedule timestamp also needs care: a reschedule must revise the same event,
  not leave the old event active as a second identity.
- `src/forex/ecb_macro.py` preserves a fixed HICP sample and raw hash, but
  `includeHistory=true` alone does not establish when each value became known.
  Per-revision availability needs verification before intraday replay.
- `src/forex/event_quality.py` provides useful revision, cancellation and DST
  checks. Its duplicate/conflict handling must be tested for ordering invariance:
  conflicting records cannot become authoritative merely by arriving first.
- `scripts/capture_m21_evidence.sh` calls `fixture_records()`. Its quality drill
  does not demonstrate a continuously maintained calendar or publisher data
  ingestion. Source labels on fixtures are not captured publisher observations.
- `src/forex/simulated_risk.py` checks supplied event windows but permits an
  empty list; it has no evidence that an empty list means a healthy, quiet feed.
- `t480/m20_demo_trading_session.py` explicitly supplies
  `news_blackout_inactive=True` in its current decision path. The simulated
  blackout functionality does not establish deployed event protection.
- Existing M8/M9/M10/M21 logic and Wave 2/M20.14 plans are the starting points.
  Extend them through one work package rather than create another competing
  roadmap or rebuild the strategy/risk engine.

These are source observations, not a new audit of all deployed services or the
current size of the database. The earlier claim that the whole database contains
only 720 bars was broader than the inspected historical documentation supports.

## Smallest useful first release

Coverage is EUR/USD and four event families: US CPI, US Employment Situation,
FOMC policy decisions (with associated press conferences), and ECB policy
decisions (with associated press conferences). Register Euro-area flash HICP as
the next addition. A limited calendar must advertise its exact scope; it cannot
claim comprehensive news protection. GDP, PCE, PMIs, speeches and unscheduled
news remain explicit coverage gaps until separately qualified.

Start with one real BLS calendar ingestion from publisher retrieval through
storage and an operator report. Complete the four-family coverage contract
before claiming the initial EUR/USD event layer is ready. Date-only meeting
calendars need an independently sourced release time before intraday use.

The operator report should answer: what is scheduled in the next seven days,
when it occurs in UTC and Pacific/Auckland, whether all required sources are
healthy, when information was collected, and which configured event window
would affect the next candidate. Show source links and explicit unknowns.

## Module and data boundary

```text
Publisher adapters -> immutable captures -> event revisions + source health
                                             |
                                      as-of context query
                                       /             \
                              Forex event policy   offline replay
                                       |
                              candidate annotation
```

One library, one command-line collector/report, and the existing database are
sufficient. Begin with three logical records: source capture, event revision,
and source coverage/health. A durable scheduled job runs independently of an AI
conversation. Avoid a new web service, message bus, vector database, analyst
agent or general-purpose macro prediction engine in this release.

An event revision contains stable source/event identity, event family,
country/region, affected currencies, reference period, source schedule and
timezone, normalized UTC schedule, status, revision, publisher publication time
when known, first observed time, ingestion time, source URL, terms reference,
and raw artifact hash. Later actual/previous/consensus observations need their
own availability and revision records, plus units and seasonal-adjustment basis.

The query accepts both a decision cutoff and a future schedule horizon. It can
return next week's known schedule, but only revisions observed by the decision
cutoff. A reschedule or cancellation never overwrites past knowledge. Preserve
publisher publication time separately from local availability; historical
downloads made today cannot be represented as observations collected years ago.

Return `coverage_status`, covered families and interval, source freshness,
snapshot ID and matching events. Forex maps this to `CLEAR_WITHIN_COVERAGE`,
`EVENT_WINDOW` or `CONTEXT_UNAVAILABLE`. An empty result without a successful
coverage check is unavailable. Candidate annotations include the exact context
snapshot and policy version for reproducibility.

For the proposed pilot, retrieve upcoming schedules daily and refresh before
the configured Forex entry session. Use a versioned, initially 24-hour maximum
retrieval age and a seven-day requested horizon; test source publication cadence
and narrow these settings if needed. A fresh HTTP response alone does not prove
complete or correct coverage. Retries are bounded; stale snapshots remain
visible and cannot silently extend their expiry. Avoid aggressive polling of
public publisher sites. This cadence is for schedule awareness, not low-latency
actual-value delivery.

## Data source choices

- BLS offers an official iCalendar feed suitable for initial US CPI/employment
  schedule ingestion: https://www.bls.gov/help/hlpiCAL.htm
- The Federal Reserve publishes meeting calendars and linked releases:
  https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- ECB publishes policy decisions and a release-time statement. Its terminology
  and DST interpretation must be verified against actual dated releases:
  https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html
- Eurostat offers a release calendar for the later flash-HICP addition:
  https://ec.europa.eu/eurostat/web/main/news/release-calendar
- FRED warns that release dates do not necessarily indicate website
  availability. Use its vintage data for research, not inferred intraday delivery:
  https://fred.stlouisfed.org/docs/api/fred/release_dates.html
- Trading Economics documents actual, previous, forecast and revised calendar
  fields, with a separate TEForecast field:
  https://docs.tradingeconomics.com/economic_calendar/snapshot/
  This is a candidate if maintaining official sources becomes costly or
  consensus-based research is justified. Price, storage/replay rights, coverage,
  latency and historical forecast vintages need qualification before purchase.
  A current historical endpoint is not automatically an as-of forecast archive.

Official calendars provide useful schedules without requiring a commercial
consensus feed. Check each source's terms and automation access before deploying
collection. Count maintenance time as a cost when comparing free and paid feeds.

## Connecting economic events to decisions

First annotate eligible Demo candidates with event proximity and coverage
health. Evaluate the existing policy and one predeclared event-filtered variant
with the same costs, sizing and exit rules. Reuse the shared policy/replay work;
simply removing old executed trades misses positions that would have become
eligible under the changed policy. Keep actual broker outcomes distinct from
simulated alternative outcomes.

The current configured 30-minute blackout can be a baseline research setting,
not an optimized claim. Test the decision horizon as well as the entry instant
and define how existing protected positions are handled before enabling a rule.
Unavailable required context should block new entries once the policy is
activated, while existing position protection continues.

Later, one actual-versus-consensus study can ask whether a surprise predicts
returns at a specified horizon after costs. Consensus must have been retained
before release and matched by units/reference period. Missing consensus means
unknown surprise, not zero. A positive economic surprise is not a universal
BUY/SELL mapping; direction and stability must be evaluated for the pair and
horizon. Defer LLM sentiment and automatic strategy switching.

## Delivery and acceptance

1. Data slice: qualified real publisher capture, stable identities, append-only
   revisions, idempotent ingestion, source-health recording and seven-day report.
   This can be built and verified while FX markets are closed.
2. Coverage and replay: complete the four-family mapping; exercise DST gaps and
   folds, reschedules, cancellation, conflicting duplicates, source outage,
   partial coverage, stale caches, timestamp errors and historical as-of queries.
   Demonstrate them with behavioral tests and retained real source captures;
   injected failures remain explicitly labelled test evidence.
3. Demo integration: record event context alongside decisions when fresh quotes
   return. Review observed timing and policy behavior, then enable a separately
   versioned deterministic entry filter after the existing execution gates pass.

The first useful handoff is a working, auditable EUR/USD event report and a
replayable context function. Defer UI polish, extra asset classes, every macro
series, consensus subscriptions and event-direction models. Set a development
time budget and report source blockers early; do not promise release readiness
before source quality has been observed. The first two steps are independent of
market opening. No order or return is needed to prove event-data plumbing.

Measure scheduled-event coverage, timing correctness, downtime, operator minutes,
and recurring cost first. Measure return/drawdown impact separately through the
existing frozen research process. Avoid adding an ongoing subscription whose
benefit has not been evaluated against the operator's modest income objective.

## Parked execution work and corrections

At Chris's request, M29 is recorded BLOCKED using the governance CLI. M27/M28
retain NEEDS_REVALIDATION; M30-M32 remain PLANNED; M20 retains its explicit
HUMAN_REVALIDATION_EXCEPTION. This is an execution-proof pause, not a waiver.
The current request authorizes this independent review; production event-layer
implementation should use the scoped package above and an explicit scope record
without pretending it proves a future execution milestone.

Monday is the intended resume window, conditional on observed fresh Demo
quotes and verified time handling. No exact opening time or automatic restart
is asserted. Parking milestone work does not stop or restart the existing
Windows listener, change trading leases, or alter any background monitor.

Two earlier implementation claims need correction before closeout. The M27
nearest-of-UTC+2/UTC+3 rule cannot independently establish the broker offset:
a quote one hour stale under UTC+3 can look fresh under UTC+2. The prior frozen
quote observation was not proof of a seasonal change. M29's millisecond client
timeout does not establish interrupted collection, durable restart recovery or
persistent deduplication, and its verifier trusts derived declarations without
fully cross-checking the raw envelopes. Market reopening alone cannot repair
these gaps; both require code remediation and independent verification.
