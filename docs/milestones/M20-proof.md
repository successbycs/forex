# M20 — Ollama-assisted historical evaluation

M20 compares a bounded local Ollama sentiment observation with two fixed
historical comparators. It is a small research evaluation, not a strategy,
signal, order, forecast, profitability claim, or live-trading capability.

## Fixed T480 evaluation

```text
M2 retained Demo-only EUR/USD H1 snapshot (720 closed bars)
  -> first three complete chronological UTC 08:00-to-20:00 sessions
  -> twelve closed bars per session -> fixed qwen2.5:3b JSON sentiment request
  -> validated sentiment label / invalid output becomes ABSTAIN
  -> compare with two-bar price direction and NO_TRADE
  -> cost-sensitive descriptive totals
```

The controls are pre-declared in `forex.m20.ollama-historical-evaluation.v1`:
exactly three sessions, strict chronological order, no shuffling, twelve bars of
bounded historical context, a two-basis-points-per-side sensitivity for
directional labels, and `NO_TRADE` as a comparator. An invalid model response
is a non-actioning abstention. A fixed harmless local warm-up runs before the
three observations. Each model call is then bounded to 180 seconds, so a
slow local inference is recorded as the same non-actioning abstention rather
than holding the T480 workflow indefinitely.

M20 proof requires at least one schema-valid, research-only local-model
response. Three timeout-derived abstentions prove the fallback but do not prove
the Ollama-assisted comparison.

Because the retained M2 observation has one snapshot-capture timestamp rather
than a source observation time for each bar, M20 uses the already documented
M16 `RETROSPECTIVE_H1_BAR_CLOSE_ASSUMPTION`: a closed H1 bar is treated as
available one hour after its timestamp. This makes the chronological research
comparison possible but is not evidence of real-time availability.

The fixed `forex-m20-ollama-evaluation-probe` adapter command takes no caller
arguments. It reads PostgreSQL and calls only the approved local
`qwen2.5:3b` container. It cannot access MT5, accounts, credentials, a live
broker server, order placement, or any execution surface.

Results are descriptive for a very small, retained historical sample. They do
not establish an edge, realistic execution costs, forward performance, or a
recommendation to trade.
