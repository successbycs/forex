# M13 proof

M13 aligns historical EUR/USD bars and context records using their recorded
`available_at_utc` timestamp. A replay cutoff includes only records known at or
before that UTC instant; later records are excluded. The fixed T480 drill proves
this boundary with a visible accepted/excluded context pair. It has no trading,
forecast, model, order, or live-data capability.
