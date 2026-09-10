# FX trading edge: research review and proposed update wave

> Historical source review and initial proposal. For corrected source analysis
> use the [10 September literature review](2026-09-10-fx-literature-source-review.md).
> Future work follows the [current numbered waves](../docs/prompts/demo-income-waves.md),
> which supersede the R0/E1–E6 execution sequence in this original proposal.

Date: 7 September 2026
Status: Research and proposed work; not an executed wave or proof of profitability.
Origin: Chris's supplied Claude analysis, followed by the primary-source searches and repository observations discussed in this conversation.

## Mission

Develop a system capable of modest, sustainable returns after trading and operating costs, within explicit capital-risk boundaries and with low operator effort. Capital preservation takes priority over trade frequency. Whether this repository can meet that mission remains unproven.

The immediate recommendation is to measure broker-specific costs and test a small number of predeclared hypotheses. Published findings help choose experiments; they do not establish an edge for this broker, account, instrument, or implementation.

## Review of Claude's analysis

Claude's central warning is well supported: published currency-factor results do not validate the repository's EUR/USD M1 technical rules. However, it would be too strong to conclude that every intraday rule must fail or that a slower rule will necessarily succeed.

| Claim | Assessment | Implication for this repository |
| --- | --- | --- |
| Cross-sectional currency momentum has empirical support. | Menkhoff et al. report a winner–loser excess-return spread of up to 10% annually, partly explained by costs, with substantial limits to exploitation. This is a portfolio result, not an expected return on a retail trading account. | A diversified monthly benchmark is a useful later research comparison. It does not justify adding EUR/USD M1 trades. |
| Time-series momentum supports slower trading. | Moskowitz, Ooi and Pedersen find return persistence over one to twelve months across 58 liquid futures instruments, including currencies. | The cited paper does **not** establish an H1 trend-filter edge. H1 alignment is a separate hypothesis to test. |
| Realistic costs undermine intraday technical rules. | Neely and Weller find no excess returns for the intraday rules they study after realistic transaction costs and trading hours. | Assess executable, net returns. Forecast accuracy and gross backtest profit are insufficient. |
| The London–New York overlap is attractive. | BIS describes concentrated activity during the overlap and thinner activity during late New York/early Asia hours. | Treat session selection as an execution-quality hypothesis. High liquidity alone does not predict direction or profit. |
| Use a fixed 13:00–17:00 UTC overlap. | A fixed UTC interval does not handle London and New York daylight-saving transitions. | Use local session calendars and test transition weeks explicitly. |
| Off-session spreads are 10–100 times worse. | That magnitude was not established for this broker's EUR/USD feed in this review. | Measure it; do not use it as an assumed cost multiplier. |
| One hundred out-of-sample trades establish an edge. | A trade count alone cannot establish economic or statistical reliability, especially when trades are dependent. | Require calendar coverage, dependence-aware uncertainty estimates, a frozen holdout, and sufficient effective sample size. |
| Testing many strategies requires data-snooping correction. | Sullivan, Timmermann and White evaluate performance against the full tested rule family using a Reality Check bootstrap. | Retain unsuccessful variants and account for selection. A significance test cannot repair leakage or repeated holdout tuning. |

The original Claude material also discussed carry, value, time-of-day directional effects, and recent machine-learning studies. Those claims were not all independently examined in the follow-up search. They remain leads for further research, not approved execution rules. In particular, carry introduces financing and tail-risk questions that require separate evaluation.

## Sources examined in the conversation

- [Menkhoff, Sarno, Schmeling and Schrimpf (2012), Currency Momentum Strategies — author institutional repository](https://openaccess.city.ac.uk/id/eprint/3296/): cross-sectional results, transaction costs, and limits to arbitrage.
- [Moskowitz, Ooi and Pedersen (2012), Time Series Momentum — published paper hosted by Yale](https://fairmodel.econ.yale.edu/ec439/mosk.pdf): futures evidence and its one-to-twelve-month horizon.
- [Neely and Weller, Intraday Technical Trading in the Foreign Exchange Market — author-uploaded working paper](https://www.researchgate.net/publication/5047834_Intraday_technical_trading_in_the_foreign_exchange_market): intraday rules after realistic costs and trading-hour restrictions; subsequently published in 2003.
- [BIS, The Foreign Exchange Market, Working Paper 1094](https://www.bis.org/publ/work1094.pdf): market structure and intraday activity patterns.
- [Sullivan, Timmermann and White, Data-Snooping, Technical Trading Rule Performance and the Bootstrap — CEPR discussion paper](https://cepr.org/publications/dp1976): correction across a complete family of tested technical rules. Its empirical application is equity data; the statistical method is the relevant contribution here.
- [Burnside, Eichenbaum and Rebelo, Understanding the Profitability of Currency-Trading Strategies — NBER](https://www.nber.org/reporter/2012number3/understanding-profitability-currency-trading-strategies): authors' overview of diversified, monthly carry and momentum portfolios.

These sources support research priorities, not a current profitability claim. This document preserves the conversation's review; it is not a systematic review of every source in Claude's bibliography.

## Repository implications and suggestions

1. **Finish trustworthy execution first.** The four recovered legacy Demo attempts totalled AUD -0.58 after recorded broker charges. That recovery repairs attribution; four trades provide no useful evidence of a sustainable edge. Wave 1 still requires its remaining real-world lifecycle and risk-drill proof. See the [Wave 1 handover](../docs/milestones/demo-income-wave-1-report.md).
2. **Make costs measurable before adding signals.** Existing historical outcomes with unknown broker fees are excluded from profitability reporting. Keep actual fills, commission, fee, and swap distinct from spread/slippage estimates. Actual fill P&L already reflects execution prices; subtracting those estimates again would double-count costs.
3. **Measure economic viability for the human operator.** Report both net trading P&L and net operating income after attributable data, API/model, hosting, and other recurring expenses. State the capital assumption and whether tax is excluded. Demo balances are not evidence of deployable capital or income.
4. **Test session selectivity.** Compare broker execution quality and net outcomes across London, overlap, New York, Asia, and rollover periods. Avoid selecting the best-looking session retrospectively and calling it out-of-sample evidence.
5. **Test H1 alignment in shadow mode.** A slower context filter may reduce weak M1 trades, but it may also discard profitable ones. Compare filtered and unfiltered decisions at equal risk using data available at each decision time. Reuse existing observational M5/H1 context where suitable.
6. **Keep the hypothesis family small.** Predeclare rules, parameter variants, cost assumptions, and promotion criteria. Retain every attempted variant, including failures. Treat a finding of no viable candidate as a valid result.
7. **Use a diversified factor benchmark as a later comparison.** A monthly G10 momentum benchmark can test whether the single-pair intraday focus is worth retaining. It requires separate data and scope approval; no multi-currency trading authority follows from this recommendation.

## Proposed wave: Edge Discovery and Cost Validation

This proposal is not a replacement for the approved wave plan. Its execution should follow the remaining Wave 1 proof and risk drills and be mapped into the existing contracts before implementation. Numerical observation windows below are proposed collection checkpoints, not profitability thresholds.

| Activity | Change and why it is needed | Definition of success | Real-world demonstration |
| --- | --- | --- | --- |
| E1. Fee-complete outcome gate | Require complete broker cost attribution before including an outcome in performance evaluation. | Every evaluated close has exact broker deal linkage, commission, fee, swap, and realized AUD P&L. Unknown costs remain visibly unavailable. | Independently reconcile 20 consecutive post-release closed Demo outcomes to retained broker history. This tests accounting completeness, not an edge; do not force trades to reach the count. |
| E2. Broker session-cost map | Measure spread, slippage, rejection rate, and net results by daylight-saving-aware session. | A versioned report shows sample counts, uncertainty, missingness, and cost distributions, with explicit assumptions for unobserved fills. | Collect six weeks of bounded Demo observations and eligible executions without changing the session hypothesis during collection. Extend collection if coverage is insufficient. Respect current retention rules; a continuous tick store would require a separate scope change. |
| E3. H1 alignment shadow experiment | Record one predeclared H1 trend hypothesis beside M1 decisions, reusing existing context where possible. | A reproducible comparison measures the incremental effect of filtering, after costs and at comparable risk. Opposing or neutral context has no new execution authority during the experiment. | Replay an untouched chronological holdout and collect prospective shadow decisions. Label counterfactual fills as simulated; only executed Demo orders provide broker-fill evidence. |
| E4. Hypothesis registry and selection correction | Record all tried variants and use a dependence-aware Reality Check or Hansen SPA procedure appropriate to the return series. | The tested family, benchmark, split dates, block/bootstrap choices, and promotion rule are frozen before final evaluation. Failed variants remain in the record. | Independently reproduce the analysis from retained data, including a flat/no-trade benchmark and the current M1 baseline. A benchmark using buy-and-hold FX must specify financing and exposure. |
| E5. Net-expectancy and operating-income gate | Replace win-rate or gross-profit promotion with a net economic decision. | A candidate passes predeclared uncertainty, drawdown, cost-stress, and operating-cost criteria. Insufficient evidence produces an inconclusive result. | Combine an untouched historical holdout with a prospectively frozen Demo evaluation. Reconcile observed fills and charges, test adverse cost assumptions, and report net income at the stated capital. No fixed trade count alone triggers promotion. |
| E6. Diversified factor benchmark, shadow only | Calculate a simple monthly currency-momentum comparison to test the value of the present single-pair focus. | A reproducible benchmark reports financing, turnover, costs, exposure, and drawdowns at comparable risk. | Use attributable historical data and prospectively retain monthly shadow decisions. Simulation and shadow results cannot demonstrate broker execution. This is a separate research scope extension, not multi-currency deployment. |

## Evaluation boundaries

- Keep real-world execution on `GOMarketsMU-Demo`; `GOMarketsMU-Live` remains prohibited.
- Preserve the approved Conservative Option B capital-risk boundaries throughout evaluation.
- Freeze the final holdout and prospective evaluation rules. Do not tune after seeing their results and reuse them as fresh proof.
- Bootstrap at a time-block level suitable for dependent returns; a confidence interval based on independent trades may materially overstate confidence.
- Predeclare confidence level, multiplicity treatment, cost stresses, drawdown limits, and minimum calendar coverage before running the promotion assessment. A requirement for a positive lower confidence bound remains a proposal until these details are specified.
- Demo execution validates the Demo implementation and cost observations. It does not establish identical live fills, financing, or future returns.
- Avoid adding more M1 patterns or ML models until a small baseline experiment can demonstrate a credible incremental benefit after costs.

The practical research priority is to determine whether selective participation improves net expectancy enough to cover operating costs within the approved risk budget. Session quality and slower context are candidates to test, not established sources of profit.
