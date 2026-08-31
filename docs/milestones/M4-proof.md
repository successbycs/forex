# M4 — historical research application boundary

`forex.research_data.historical_bars` is the MVP application interface for
validated historical snapshots. It is read-only and point-in-time constrained.
It does not connect to MT5, PostgreSQL, a network, accounts, or orders.
