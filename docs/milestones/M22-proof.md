# M22 — deterministic simulated risk engine

M22 evaluates only offline intents. Its fixed policy permits EUR/USD only,
one position at most, a planned AUD loss no greater than 100, a 12-point spread
ceiling, a strict 18:00 UTC flat-by cutoff, and a 30-minute scheduled-event
blackout. Each result is bound to hashes of the two canonical policy files.

The only approval outcome is `APPROVE_SIMULATION`; it has no broker, MT5,
credential, shell, position-sizing, or order-submission surface. Every unsafe
input produces `REFUSE` and an inspectable reason. Event context must already
be qualified and available at the simulated decision cutoff.
