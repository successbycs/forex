# M1 decision-workflow end-state review

## Decision

Define the smallest meaningful end state for the repository's EUR/USD M1 Demo
decision-and-learning workflow. The end state is a reproducible, controlled
Demo operation; it is not a claim that any strategy will be profitable and it
does not include Live trading.

## Recommended end state

The end state is one candle-keyed M1 decision loop that produces one
explainable `BUY`, `SELL`, or `NO_TRADE` result from only point-in-time inputs.
An actionable proposal is persisted before one fixed `GOMarketsMU-Demo` order
is submitted. Every decision, refusal, order, protection value, lifecycle
event, broker close, cost, and realised outcome is linked to the same snapshot,
strategy/version, configuration, and idempotency identity.

The loop must remain useful when it does not trade. `NO_TRADE` reasons show
whether data, calendar, cost, financing, risk, exposure, or strategy selection
prevented an entry. Retained outcomes support later research; they do not
automatically change a strategy or increase risk.

## End-state components

| Component | End-state behaviour | Current direction |
| --- | --- | --- |
| Trigger | One decision key per completed M1 candle with a bounded fresh quote. | Needs an explicit candle-keyed contract; the listener currently runs every five seconds. |
| Data | Completed, fresh, UTC-bound M1 data and executable bid/ask are retained as a decision snapshot. | Present. |
| Safety | Demo identity, hold, lease, account, position, recovery, risk, and duplicate-order checks fail closed. | Present. |
| Event risk | Qualified USD/EUR event context can veto new entries; unavailable required context also vetoes. | Interface exists; shipped policy is annotation-only. |
| Strategy decision | Five versioned M1 assessments produce at most one selected owner and explicit refusal reasons. | Present. |
| Higher timeframes | M5/H1 are retained as point-in-time shadow context; they have no M1 authority until evidence supports promotion. | Present as shadow context. |
| Execution | Persisted proposal plus idempotency reservation permits at most one protected Demo submission. | Present. |
| Lifecycle | Monitor, required exit behaviour, broker close, costs, and reconciliation are retained. | Present; M30 needs fresh real-system proof. |
| Learning | Outcomes are attributable to strategy, snapshot, costs, event context, and regime for pre-declared research. | Core records exist; a unified analysis scorecard remains future work. |

## Evidence-led promotion rules

The following are reasonable safeguards, not proof of a trading edge:

1. Treat M5/H1 and event context as shadow inputs first. Compare a locked base
   M1 workflow with pre-declared filtered variants using only data available at
   each decision.
2. Include observed/defensible spread, commissions, slippage, financing, and
   trading-session constraints. Technical-rule results can disappear after
   realistic costs.
3. Keep a holdout or walk-forward period and account for searching across many
   strategies, parameters, or filters. Do not promote a filter solely because
   it improved an in-sample result.
4. Promote a shadow input to a veto only when the result is reproducible,
   cost-aware, and operationally explainable. A promotion needs explicit
   configuration, tests, deployment, and milestone authority.

Scheduled macro surprises can cause abrupt FX price changes, supporting a
conservative event-risk control but not a directional prediction rule. Academic
results on intraday technical rules are mixed and sensitive to realistic costs
and model selection. See [Andersen et al.](https://public.econ.duke.edu/~boller/Published_Papers/aer_03.pdf),
[Neely and Weller](https://www.sciencedirect.com/science/article/pii/S0261560602001018),
[Park and Irwin](https://experts.illinois.edu/en/publications/what-do-we-know-about-the-profitability-of-technical-analysis/),
and [White](https://doi.org/10.1111/1468-0262.00152).

## What is not part of this end state

- Live trading, `GOMarketsMU-Live`, or a generic broker interface.
- A claim that a successful Demo outcome demonstrates future profitability.
- Automatic parameter optimisation, automatic risk expansion, trailing-stop or
  partial-exit features without an explicit future strategy/lifecycle change.
- M15 authority. M15 remains a separately scoped future timeframe extension.

## Next actions

1. Commit the operational workflow, diagram, and review documents so a clean
   revision can run the scheduled M30 capture.
2. Complete M30's bounded Demo order, close, reconciliation, and offline
   evidence verification.
3. After M30 and a new explicit milestone, define the candle-keyed trigger and
   run event/M5/H1 filters in shadow evaluation before deciding whether either
   becomes an active veto.
