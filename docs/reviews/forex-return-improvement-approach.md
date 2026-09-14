# Forex return-improvement approach

Sequencing superseded on 2026-09-12 by the operator-directed
[shared wave guide](../prompts/demo-income-waves.md) and
[Wave 3](../prompts/demo-income-wave-3.md): retain M1 and add one longer-hold
Demo stream after operational checks, without a profitability prerequisite.
The research below remains rationale, not authority to reinstate H_EVENT-first,
mandatory shadow-performance or economic-support-before-Demo gates.

Review date: 2026-09-12. Requested by Chris following the economic-event layer
review. This is a targeted comparison of publicly documented systematic
approaches and trading-engine practices from international researchers and
providers. It is not an exhaustive global survey, a replication, a verified
ranking of funds, or a claim of access to proprietary strategies. No new
backtest or trading experiment was run for this review.

## Recommendation for this operator

Stay with Forex, the current repository, the existing Demo executor and one
small event module. Make the next research result a reproducible comparison
of the frozen current EUR/USD policy with one event-aware variant. Follow it
with one slower trend candidate if historical data and financing can be
qualified. Prefer a short list of falsifiable hypotheses to more concurrent
strategy development. No source reviewed establishes that either candidate
will improve this account's returns.

Improvement means higher net operator benefit at matched feasible capital and
risk, with tolerable drawdown and maintenance effort. Losing less than the
baseline is useful information but is insufficient to justify trading when
the no-trade alternative is better. Do not raise risk to satisfy an income
target or treat an operational milestone as evidence of economic value.

## What the international evidence supports

| Approach | Public evidence and limitations | Fit for this Forex project |
| --- | --- | --- |
| Slower trend following / time-series momentum | Moskowitz, Ooi and Pedersen study own-market return persistence across futures/forwards. Hurst, Ooi and Pedersen extend historical trend evidence across assets. These are diversified historical studies, not a retail EUR/USD income forecast. [S1, S2] | Best next directional research family on methodological fit: simple rules, lower turnover, modest computation. Single-pair performance, whipsaws and broker financing require separate testing. |
| Cross-sectional currency momentum | Menkhoff et al. find winner/loser currency return differences, with costs and limits to exploitation. [S3] | A later Forex diversification candidate. Cannot reproduce a multi-currency ranking strategy on one pair. Adding several USD pairs also creates shared USD exposure. |
| Currency carry | Carry research links returns to global FX volatility risk and adverse outcomes during volatility increases. [S4] | Poor first choice for a small steady-income objective. Actual retail swaps, funding changes and tail losses matter; policy-rate differences are not broker cash credits. |
| Systematic macro | Brooks describes macro-trend positioning as a global systematic approach. This is manager-authored historical material, not independent evidence of current implementability. [S5] | Useful later research direction after vintage data, units, horizons and revisions are reliable. No need for a broad macro model in the first release. |
| Scheduled-event / news trading | Andersen et al. link announcement surprises to exchange-rate jumps. That establishes an information relationship, not a profitable retail reaction strategy after latency and costs. [S6] | Start with event timing and entry eligibility. Defer directional surprise trading until pre-release consensus and actual arrival times are retained. |
| Intraday technical rules / session effects | Neely and Weller find no excess returns for their tested intraday rules after realistic costs/hours; other daily-rule research by Hsu et al. reports positive results with estimated costs and selection controls. Ranaldo documents time-of-day patterns. Different samples and horizons matter. [S7–S9] | Keep the existing M1 policy as the measured baseline. Neither reject all technical methods nor assume the current five rules have an edge. Session effects justify a hypothesis, not a universal preferred window. |
| Institutional execution algorithms | BIS describes how execution algorithms route execution across fragmented FX markets and affect execution risk. This is a different task from generating directional profit forecasts. [S10] | Borrow execution-cost measurement, reconciliation and observability. Do not build institutional routing or compete on subsecond news access through the current remote terminal. |

These sources span central-bank and international research, academic work and
manager research. Many are older studies: they are candidate-generation and
methodology evidence, not proof that an edge persists in 2026. Provider papers
have commercial incentives. AQR's historical research is not a promise from
AQR, and the figures from diversified portfolios cannot be assigned to a
single-pair leveraged account.

## Trading engines: practices worth borrowing

MetaTrader's tester supports broker real-tick history and forward splits, but
its documentation also describes generated-tick substitution when history is
incomplete. Its profit-in-pips mode omits swap, commissions and margin control.
Check actual coverage and test settings before treating a report as an
economic result. Its forward split is historical out-of-sample testing, not
prospective Demo execution. [S11, S12]

LEAN makes fees, fills, slippage and other broker behavior explicit models.
That is a useful design pattern. Defaults still require scrutiny: documented
slippage models can return zero where volume is unavailable. A framework
cannot establish realistic Forex costs just by being installed. [S13, S14]

For now use the existing Python research code and MT5 adapter. The repo already
has `src/forex/m20_policy_kernel.py`; qualify and reuse it rather than promise
a second new engine. It is a pure representation of current logic, which is
not yet proof that every research/execution path is equivalent. MT5's tester
does not directly execute the Python listener's whole audit/risk workflow;
porting rules to an Expert Advisor creates another parity obligation.
An immediate LEAN migration or separate event service adds work without
establishing better returns.

## Concrete weaknesses in the current policy

The inspected runner selects among five EUR/USD M1 rules with shared inputs
and precedence. These are correlated candidates rather than five independent
sources of return. Owner exits are six to ten minutes. There is no evidence
here that this horizon is economically appropriate for the observed costs.

`t480/m20_demo_trading_session.py` explicitly sets `news_blackout_inactive`
to true without a calendar source. Its `abnormal_volatility_inactive` gate
uses spread, not an independent price-volatility measurement. Naming a gate
does not establish its intended protection. Fixing or introducing these
behaviors would be a versioned policy change.

The cost-coverage calculation estimates the net amount at the proposed take
profit. It is not expected return. For example, purely hypothetically, a
policy winning 40% of the time at 1.5 initial-risk units and losing 60% at 1
unit has zero gross expectancy before costs. A plausible target can coexist
with a losing policy. The actual calculation must include breakeven exits,
partial fills, time exits and the whole outcome distribution.

The current economic-event groundwork is useful but limited; the companion
review identifies sample-only coverage and fixture-based M21 evidence.
The previous claim that exactly 720 bars constitute the whole current database
was not established by a live inventory. Inventory and qualify what exists
before buying data or collecting it again.

## Defined experiment sequence

### 1. Freeze and explain the baseline

Resolve the identified timestamp/recovery proof defects before operational
closeout. For economic analysis, reconcile every retained attempt and closed
outcome in a declared period, including rejected and unknown states. Bind
strategy, sizing, stops, exits, costs and risk pauses to one version. Produce
an input coverage report before calculating performance.

Use cash-flow-adjusted marked-to-market account returns on common calendar
dates, including no-trade days and unrealized exposure. Report actual broker
net separately from attributed costs and simulation. Actual fill-to-fill P&L
already includes execution-price effects; subtracting spread estimates again
would double-count costs. Unknown charges remain unknown.

### 2. First challenger: H_EVENT, an event-aware entry policy

Proposed research definition: use the identical frozen baseline and all of its
existing eligibility rules, with one additional deterministic check. For the
initial four-family event coverage (US CPI, US Employment Situation, FOMC and
ECB policy decisions plus associated press conferences), reject a new entry
if its interval from decision time through the owner's maximum permitted hold
intersects an event window from 30 minutes before through 30 minutes after
the scheduled release. Boundaries are inclusive. Use the repo's current
30-minute setting as a declared starting point, not a searched optimum.

At decision time, require a healthy snapshot covering every declared family
and the requested horizon. Missing, expired, conflicted or partial coverage
means no new entry. Existing position protection and owner exits continue.
No event-based forced close is introduced. Schedule amendments must use the
version known at decision time. Rescheduled events and new cancellations
must not retrospectively change earlier decisions.

This is a project hypothesis: reducing entry exposure near announcements may
avoid costs or losses, but can also remove profitable opportunities. Maintain
independent policy account paths. Dropping selected baseline trades from a
spreadsheet misses trades enabled by different position availability and
risk-budget usage. Compare policies over common dates and matched costs/risk.

The current Wave 3 plan names H_SESSION and H_SLOW as its two challengers.
This review proposes replacing H_SESSION with H_EVENT because the user has
prioritized the event layer. It does not silently amend or execute that plan.
Record the replacement before research trials; existing exploratory session
work remains in the search history. Do not add event × session × trend grids.

### 3. Second challenger: H_SLOW, one slower trend rule

Prioritize a daily-observed, monthly-rebalanced 12-month momentum reference
for research, inspired by S1. For a single-pair spot-direction adaptation,
the sign of the completed 12-month EUR/USD price change selects long or short
EUR; a zero change selects flat. Evaluate after a completed month and act
only at the next eligible observed quote. This is an adaptation, not an exact
replication of a diversified futures/forward excess-return strategy.

The deployment-ready specification still needs predeclared sizing,
volatility estimation, protective stop, financing, gap handling and exit
semantics under feasible retail lots. These must be frozen before evaluation
and included in its trial record. Qualified long-history and broker financing
coverage are prerequisites; do not claim a completed H_SLOW study from an
unfunded spot-return chart. Do not optimize numerous lookbacks on the holdout.

The current execution mandate exits after minutes and excludes overnight
holding. H_SLOW is therefore offline research until a separate holding-policy
qualification and Demo mandate exists. It cannot be inserted into the current
listener merely by adding another indicator. Lower turnover reduces repeated
execution charges for comparable exposure, but financing and sustained losses
can offset that benefit. It is the stronger next research family, not an
already-qualified replacement.

### 4. Decide from complete economic evidence

Use the existing Wave 3 research process instead of adding another milestone
series: chronological development, untouched final evaluation and subsequently
observed Demo/shadow results. Account for every trial and abandoned variation.
Use the predeclared family-comparison and uncertainty procedure already
specified there; do not select the statistical test after seeing results.

Judge improvement against BOTH the frozen baseline and a feasible no-FX/cash
alternative at the same evaluation capital. Freeze the cash benchmark source,
fees, return definition and capital assumptions before comparison. A zero
trade cash comparator still needs an explicit expense convention. Report
net AUD, drawdown, time underwater, loss streaks, turnover, event coverage,
operator minutes, and uncertainty alongside risk-adjusted measures.

Include base, +50% and 2x variable-cost stress as predeclared engineering
scenarios (not published universal pass thresholds). Stress charges and fills,
not net P&L by an arbitrary multiplier. Require positive net operator benefit,
acceptable risk/effort and the existing precision criteria before support.
If the data cannot distinguish improvement from noise, return INCONCLUSIVE.
No trade quota or one-week profitability gate establishes a durable edge.

## Economic-event layer's role

Start with scheduled risk awareness and immutable decision-time snapshots.
Later, actual, prior, revision and pre-release consensus observations can
support one surprise-based study. Preserve units and reference periods.
Availability must reflect when the value could have reached this application.
A value revised later cannot enter an earlier backtest. Missing consensus is
unknown surprise, not zero. Publication of a surprising number does not imply
a fixed currency direction or an attainable fill before price adjustment. [S6]

The event layer can be built and qualified while markets are closed, using
real publisher schedules and retained data. Historical event outcomes may be
useful for analysis; today's calendar download is not historical proof of
what the system knew. Prospective capture will gradually repair that gap.

## Edge decay and solo-operator economics

Monitor data health and risk breaches immediately. Review economic performance
at a predeclared cadence, proposed monthly, without silently adding repeated
significance tests. Changes in costs, signal frequency and realized outcomes
trigger investigation, not automatic retuning. Retire or pause according to
frozen rules; any revised strategy needs a new version and new evaluation.
The existing risk latches remain operational controls throughout.

Set up ordinary scheduled software with exception alerts and one periodic
economic report. An LLM can help summarize research or incidents without
per-tick calls. Capture recurring data, compute and electricity expense and
operator time. For illustration only, AUD 300/month requires AUD 3,600/year:
36% of AUD 10,000 before fees or tax, or 7.2% of AUD 50,000. These are arithmetic
requirements, not attainable-return estimates or suggested capital allocations.
The user's intended capital and expense budget remain unspecified; the Demo
balance does not supply them.

Defer new pairs, carry portfolios, autonomous model switching, reinforcement
learning, latency arbitrage, grid/martingale systems and additional services.
This is a scope/fit decision, not a finding that every other strategy loses.
Keep the Forex event layer modular inside this repo as described in the
companion review.

## Near-term deliverables

1. Qualified event feed and an upcoming-event/health report for EUR/USD.
2. A complete baseline ledger/data-coverage report and replay parity checks.
3. A registered H_EVENT comparison report under the existing research process.
4. Conditional H_SLOW specification and data qualification, then its evaluation.
5. One explicit continue/revise/retire/inconclusive decision using net economics.

The first two deliverables have useful work available while market-dependent
execution milestones are parked. Live-market observation and any execution
changes retain their own proof gates. No trading setting, return target,
strategy registration or milestone contract was changed by this review.

## Sources inspected

- S1: Moskowitz, Ooi and Pedersen, Time Series Momentum (2012), author/provider
  summary: https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum
- S2: Hurst, Ooi and Pedersen, A Century of Evidence on Trend-Following Investing
  (2017), author/provider summary:
  https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing
- S3: Menkhoff et al., Currency Momentum Strategies, BIS working paper (2011;
  journal publication 2012), abstract:
  https://www.bis.org/publications/working-paper-366-currency-momentum-strategies
- S4: Menkhoff et al., Carry Trades and Global Foreign Exchange Volatility,
  author manuscript: https://openaccess.city.ac.uk/id/eprint/3391/1/CTVOL_R3_v4_paper.pdf
- S5: Brooks, A Half Century of Macro Momentum (2017), manager summary:
  https://www.aqr.com/Insights/Research/White-Papers/A-Half-Century-of-Macro-Momentum
- S6: Andersen et al., Micro Effects of Macro Announcements (NBER 2002;
  AER 2003), abstract: https://www.nber.org/papers/w8959
- S7: Neely and Weller, Intraday Technical Trading in the Foreign Exchange
  Market, January 2001 working paper, abstract/introduction:
  https://files.stlouisfed.org/files/htdocs/wp/1999/99-016.pdf
- S8: Hsu, Taylor and Wang, Technical Trading: Is It Still Beating the Foreign
  Exchange Market? (2016), author manuscript:
  https://hub.hku.hk/bitstream/10722/229640/1/Content.pdf
- S9: Ranaldo, Segmentation and Time-of-Day Patterns in Foreign Exchange
  Markets, SNB working paper (2007; journal 2009):
  https://www.snb.ch/en/publications/research/working-papers/2007/working_paper_2007_03
- S10: BIS, FX Execution Algorithms and Market Functioning (2020), report summary:
  https://www.bis.org/publications/fx-execution-algorithms-and-market-functioning
- S11: MetaQuotes, Real and Generated Ticks:
  https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation
- S12: MetaQuotes, Strategy Testing:
  https://www.metatrader5.com/en/terminal/help/algotrading/testing
- S13: QuantConnect, Reality Modeling:
  https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts
- S14: QuantConnect, Supported Slippage Models:
  https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/supported-models

Repository references: `Research/2026-09-10-fx-literature-source-review.md`,
`docs/prompts/demo-income-wave-3.md`,
`docs/milestones/demo-income-wave-2-report.md`,
`docs/reviews/forex-economic-event-layer-review.md`,
`src/forex/m20_policy_kernel.py`, `t480/m20_demo_trading_session.py`.
The existing literature review includes deeper prior readings; this update
distinguishes accessible summaries from those manuscript sources and does
not claim every referenced study has been independently replicated.
