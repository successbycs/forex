# M28 proof

M28 uses only the fixed read-only `m27_demo_tick` operation. It derives the EURUSD spread in configured MT5 points, compares it with `config/risk.yaml`'s `maximum_spread_points`, and records either `ACCEPTED_FOR_SIMULATED_INTENT_ONLY` or `SPREAD_LIMIT`. It never creates an intent, order, position, or generic MT5 command surface.
