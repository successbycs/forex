# M30 proof record

M30 proves one bounded autonomous `GOMarketsMU-Demo` `EURUSD` lifecycle. It
requires one broker-accepted entry, a terminal close caused by the configured
cutoff or an earlier risk exit, and exact broker reconciliation of that same
proposal and execution attempt. It makes no profitability or Live-capability
claim.

The raw capture command is `bash scripts/capture_m30_evidence.sh`. It invokes
only the existing fixed `m20_demo_trading_session` operation after a clean,
committed, deployed source revision and existing autonomous safety gates are
valid. The offline verifier is `bash scripts/verify_m30_evidence.sh <bundle>`.
It rejects a non-Demo server, Live reference, stale evidence, changed artifact,
unmatched proposal/attempt/lifecycle, missing terminal closure, or incomplete
reconciliation.

No M30 real-world evidence has been captured yet.
