# M8 — US macro vintage adapter

M8 uses the FRED/ALFRED observations API for the one declared initial US macro
series, `CPIAUCSL`. The caller supplies a historical decision date; the fixed
request binds both FRED real-time boundaries and `observation_end` to that date.
The normaliser rejects a response whose vintage is not bound to the request or
which includes data dated after the decision cutoff.

`FRED_API_KEY` is machine-local and ignored by Git. The M8 capture cannot run
without it. It retains only normalised values, vintage dates, the decision
cutoff and hashes—never the key. Selecting additional series or treating this
data as a trading signal is outside M8.
