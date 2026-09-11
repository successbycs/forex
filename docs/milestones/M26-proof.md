# M26 — offline execution revalidation

M26 is a simulation-only last gate. It rechecks actionable intent, risk and
sizing outcomes, approval expiry, ten-second quote freshness, 12-point spread,
market state, and the mandatory exit cutoff. Any failure returns `REFUSE`; no
market order capability exists.
