# M3 — MT5 history-depth bridge

M3 adds one fixed, read-only T480 operation: `m3_mt5_history_depth_probe`.
It asks the authenticated `GOMarketsMU-Demo` terminal for up to 100,000
**closed** EUR/USD H1 bars, excluding the current forming bar. It reports the
first and last available bar, returned count, whether the fixed request cap was
reached, and the number of invalid OHLC records.

The operation has no parameters. It cannot select another server, symbol,
timeframe, count, terminal path, Python interpreter, shell command, database
operation, account field, tick, or order method. It stores no results. M5 will
own the later idempotent persistence workflow.

If `request_cap_reached` is false, `first_bar_utc` is the earliest H1 history
available to this fixed MT5 probe at capture time. If true, the result proves
only that at least 100,000 closed H1 bars are available; it does not claim the
absolute server maximum.
