# M17 — offline non-executing context

M17 exposes a deterministic, time-bounded historical research context only. It contains closed EUR/USD OHLCV bars available by the supplied UTC cutoff plus research features. It rejects future bars and forbidden account, credential, MT5-control, order, execution, and future-data fields. It does not invoke a model, network, MT5 terminal, or trading surface.

The fixed T480 probe reads a bounded Demo-only historical sample from Forex PostgreSQL and verifies that the resulting context has `agent_authority: NONE`, `order_capability: false`, and `live_trading_capability: false`.
