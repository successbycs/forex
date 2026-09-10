# Swap-aware hold-or-close decisions

Date: 2026-09-10. Status: research and proposed specification, not deployed policy,
operator approval, trading proof or wave closeout. No runtime settings changed.
Primary papers and official documentation were located through web search;
this is not a systematic Google Scholar review. Exact paper titles below can
also be searched in Scholar.

## Conclusion and applicability

Use a conditional, cost-aware hold rule. A blanket daily exit is a provisional
operational simplification, not an established profitable policy. Retail swap
is an actual broker charge/credit; institutional carry research cannot supply
this account's swap rate or prove its EURUSD intraday strategy has an overnight
edge. A reliable swap calculator and a reliable return forecast are separate
requirements. Neither a positive swap nor a profitable open position justifies
holding on its own.

Current source inspection: `t480/m20_demo_trading_session.py` in
`_project_cost_coverage` hard-codes commission and expected swap to zero.
`_planned_stop_loss` includes stop distance and spread-based slippage, but not
financing. Historical zero-swap intraday closes do not qualify overnight costs.

## Research foundations

| Primary source | Finding relevant here | Proposed use and limitation |
| --- | --- | --- |
| Gârleanu & Pedersen (2013), [Dynamic Trading with Predictable Returns and Transaction Costs](https://onlinelibrary.wiley.com/doi/10.1111/jofi.12080), Journal of Finance | Optimal trading responds jointly to predictable returns, signal dynamics and transaction costs. | Evaluate holding and closing over the same horizon, allowing for signal decay and trading costs. Its model is not a turnkey retail-FX rollover threshold. |
| Menkhoff, Sarno, Schmeling & Schrimpf (2012), [Carry Trades and Global Foreign Exchange Volatility](https://openaccess.city.ac.uk/3391/1/CTVOL_R3_v4_paper.pdf), Journal of Finance | Global FX volatility risk helps explain cross-sectional carry returns. | Require separate downside/volatility gates; receiving financing is not evidence of low risk. Portfolio-level findings do not validate this single-pair bot. |
| Brunnermeier, Nagel & Pedersen, [Carry Trades and Currency Crashes](https://www.nber.org/papers/w14473), NBER WP 14473 (2008; revised 2013) | Carry returns exhibit negative skewness and losses associated with unwinding and funding conditions. | Stress adverse tails and liquidity deterioration, not just average swap income. |
| Ranaldo (2009), [Segmentation and time-of-day patterns in foreign exchange markets](https://www.sciencedirect.com/science/article/pii/S0378426609001265), Journal of Banking & Finance | Exchange-rate patterns differ across local and foreign working hours. | Condition research on session/time; do not assume a minute-scale signal predicts an overnight return. Historical effects need current broker-data validation. |
| White (2000), [A Reality Check for Data Snooping](https://doi.org/10.1111/1468-0262.00152), Econometrica | Selecting the best rule after trying many creates a multiple-testing problem. | Record every holding-rule trial; use an appropriate dependence-preserving reality-check/SPA procedure and untouched chronological evaluation. No fixed trade count guarantees significance. |

The rules below are our engineering synthesis, not numerical thresholds supplied
by these papers.

## 1. Measure the financing cash flow

Capture timestamped account/server, symbol, side, volume, contract size, price
point, currencies, `swap_mode`, `swap_long`, `swap_short`, triple-rollover day,
available daily multipliers, rollover schedule and conversion quotes. Confirm
broker holidays and daylight-saving effects. Do not hard-code Wednesday or a
fixed UTC hour for every instrument/account.

MetaQuotes defines multiple calculation units, including points, currencies,
interest percentages and reopening modes. Implement only the observed and
verified mode initially; unsupported or missing modes are unknown, not zero.
See [MetaQuotes swap documentation](https://www.mql5.com/en/book/automation/symbols/symbols_swaps)
and [symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants).

For a verified points mode, convert signed swap points into cash using the
instrument's price-point value and volume, apply the verified day multiplier,
then convert to AUD. Currency and interest modes require their own formulas.
Sum the expected adjustments across the declared holding horizon. Retain rate
snapshots: today's rate must not be applied retrospectively to old backtests.
Broker-specific holiday schedules and rate changes remain an uncertainty.

Keep projected swap separate from accrued/posted swap. At settlement reconcile
position/deal identifiers and signed charges exactly once, including partial
closes and any supported reopening treatment. Never add swap again if a chosen
broker total already includes it. Never subtract estimated spread again from
realised P&L already calculated from actual fills.

## 2. Compare the two actions at the same decision time

Let L(t) be the AUD net amount obtainable by liquidating now, including closing
commission and estimated execution slippage. Let L(H) be the AUD net amount
obtainable under a specified holding-and-exit policy by horizon H, including
stop-outs, take-profits, time exits and all financing through exit.

    incremental hold value = E[L(H) | information available at t] - L(t)

An operational breakdown is expected additional executable-price P&L + future
signed swap - the difference in closing costs between the two alternatives.
Already paid entry costs and already accrued swap are common/sunk components;
they belong in lifetime P&L reporting but must not be charged twice in this
incremental comparison. Add reopening costs only if close-and-reenter is an
explicit separate policy; closing now does not automatically mean reentering.

Use an estimate trained and evaluated for this exact horizon and exit policy.
A target's possible profit is not its expected profit. An LLM confidence score
is not a calibrated return forecast. Estimate uncertainty from chronological
out-of-sample outcomes with dependence accounted for.

Illustration, invented numbers: closing now nets AUD 2.00. Expected additional
price P&L from holding is +0.70; financing -0.30; extra closing friction -0.10.
Expected incremental value is +0.30, expected net outcome 2.30. If the research
uncertainty allowance is 0.40, the conservative advantage is -0.10: close.
If that financing adjustment triples to -0.90, expected incremental value is
-0.30 even before the uncertainty allowance. This is not a current broker quote.

## 3. Proposed deterministic decision gates

1. Require known, fresh, supported financing inputs and qualified return evidence
   for the proposed horizon. Otherwise refuse a new rollover-exposed entry.
2. Re-evaluate sufficiently before rollover to allow a normal exit, using a
   canonical, broker-verified cutoff and bounded retry/escalation process.
3. HOLD only if a conservative lower confidence bound on incremental value
   exceeds a predeclared net-benefit buffer AND every capital/protection gate
   passes. Avoid choosing arbitrary confidence/buffer values after viewing
   results. Defaults and calibration must be documented before evaluation.
4. Include adverse financing and execution allowance in planned stop-loss risk
   through the maximum holding period. Do not enlarge Option B risk capacity by
   netting an uncertain positive swap against a potential price loss. Assess
   tail loss/news/liquidity separately; a stop is not a guaranteed cash-loss cap.
5. Preserve valid broker SL/TP; no widening to justify overnight holding. Apply
   a maximum holding horizon and separate weekend policy. Re-evaluate on a
   material rate/risk change. A hold decision is conditional, not permanent.
6. If holding is not permitted, use the approved exit policy. For an already-open
   position with an unknown price/account or failed close, preserve protection,
   latch the appropriate incident, block new entries and retain failure evidence;
   do not label the position closed or flatten blindly from stale observations.

This policy needs an explicit approved exit/holding amendment before deployment.
The earlier question should therefore become a decision about adopting a
conditional policy, not a permanent choice between always hold and always close.

## 4. Validation and placement in the existing waves

| Wave | Narrow activity | Success and real-world demonstration |
| --- | --- | --- |
| W1 | Snapshot actual swap terms; calculate AUD financing; include it in planned risk and cost gates; reconcile actual postings; implement the approved fallback exit/holding boundary. | Compare a pre-rollover estimate with a genuine authorised Demo position's broker posting, including ordinary and triple/holiday treatment when naturally observable. Explain differences to the account's currency precision/declared rounding tolerance. Until a case is observed, label it unqualified. Local formula tests cannot replace this proof. Never force an entry or extend a trade just to obtain evidence. |
| W2 | Retain point-in-time rates, executable quotes and calendar data; replay competing hold/close policies under the same information constraints. | Reproduce observed charges and executions on retained data. Missing historical swap/spread information causes an explicit coverage gap, not a fabricated zero-cost history. Paired counterfactual outcomes are estimates, not two simultaneously observed broker executions. |
| W3 | Test always-close, bounded hold, and conditional hold on the same eligible decisions using predeclared rules and chronological evaluation. | Conditional holding must improve net results with uncertainty and multiple testing accounted for, while respecting drawdown/tail-risk and turnover limits. Run shadow decisions before promotion. If evidence is inconclusive, do not enable the claimed overnight edge. |

The operator subsequently requested incorporation of this mapping into the
canonical wave specifications; see their swap/holding subsections. Those planning
edits do not amend the milestone registry, deploy a policy or start W2/W3. No graph database, extra agent hierarchy or new trading strategy
is necessary. A small calculator, explicit policy evaluator and durable decision
record suffice. Agents may research candidates and explain decisions; deterministic
code enforces the approved money and execution boundaries.
