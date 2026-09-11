# M24 — simulated intent orchestration

M24 writes a complete offline intent record containing direction, advisory score,
calibration state, point-in-time data timestamp, entry window, mandatory exit
cutoff, invalidation conditions and risk flags. BUY and SELL are possible only
when M22 approves and M23 sizes the simulation. Every other path becomes
`NO_TRADE`; order submission is structurally disabled.
