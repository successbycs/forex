# MT5 Demo full-history import

- Captured: `2026-09-11T08:07:36.730197Z`
- Source: fixed read-only `m20_all_demo_history_export` adapter operation
- Surface: `GOMarketsMU-Demo`, AUD account, account scope hash only
- Raw wrapper SHA-256: `a7e95432653118132d6a34558a31341100becbf34c704e8f2ef2a6fa00fec4a7`
- Returned complete records: 87 deals and 84 orders, from 2000-01-01 through capture time

The raw adapter wrapper and checksum are retained beside this note. It contains
three Demo deposit records totalling AUD 101,000 and 42 closed EUR/USD deal
records whose returned realised P&L totals AUD -8.10. MT5 reported balance and
equity of AUD 100,990.83 with zero credit, leaving an AUD -1.07 difference
from deposits plus returned closed-deal P&L.

This import is raw broker-returned evidence, not a risk-anchor reset, a
cash-flow attribution, or approval to resume trading. The `EXTERNAL_CASH_FLOW`
pause remains active until Chris completes its human review.

## Superseded reconciliation interpretation

The query endpoint in this snapshot used the host UTC clock, while this broker
exposes its History-tab timestamps on a +03:00 server clock. It therefore
omitted the final three broker-clock hours, including ten 11 September closed
positions totalling AUD -1.07. The corrected complete import is in
`../mt5-demo-history-20260911T0820Z/`; it reconciles exactly to the terminal
balance.
