# M23 — simulated position sizing

M23 sizes an offline simulation only after an M22 `APPROVE_SIMULATION` result
with the same policy hash. It floors the calculated volume to the supplied
historical instrument volume step and never exceeds M22's AUD 100 planned-loss
budget. If a minimum volume would exceed that budget, or M22 refused the
intent, the result is `NO_TRADE`.

Results expose `STRUCTURALLY_DISABLED` order submission. M23 neither reads a
broker contract nor sends, suggests, or persists an order.
