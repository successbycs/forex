# Corrected MT5 Demo full-history import

- Captured: `2026-09-11T08:20Z` (read-only)
- Surface: `GOMarketsMU-Demo`, AUD, account scope verified against the account shown in the supplied MT5 History view
- Raw-export SHA-256: `79c905ba1a1ae6d55dd6a680fb009c9b6a359cc8f7509b25e5ed9f368518477a`
- Result: complete, 107 deals, 104 orders, flat account

The earlier exports used the host UTC time as MT5's history-query endpoint. This broker returns its History-tab timestamps on a +03:00 server clock, so that endpoint excluded the final three server-clock hours. The corrected exporter queries through the configured broker-clock offset while preserving the actual capture time separately.

Reconciliation: three balance entries total AUD 101,000.00; 52 closed EURUSD positions total AUD -9.17; commission, swap, fee, and credit are all AUD 0.00; reported balance and equity are both AUD 100,990.83. Thus `101,000.00 - 9.17 = 100,990.83` exactly.

The ten 11 September position tickets visible in the supplied History-tab screenshots (`42332570` through `42335362`) are all present in this export and together account for the previously unexplained AUD -1.07.

This is raw broker-returned evidence and a reconciliation note only. It does not reset a risk anchor or authorize trading.
