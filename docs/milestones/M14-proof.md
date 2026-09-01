# M14 proof

M14 is a deterministic, historical research classifier. It labels a bounded
EUR/USD bar window as `TRENDING`, `RANGE_BOUND`, `HIGH_VOLATILITY`, or
`INSUFFICIENT_HISTORY`, and applies a UTC scheduled-event blackout label.

The versioned session contract uses a daily 08:00 UTC decision timestamp and a
mandatory 20:00 UTC flat-by cutoff. It is UTC-fixed, so it does not inherit
European or US daylight-saving changes. The result is neither a forecast nor a
trade recommendation and cannot place orders.
