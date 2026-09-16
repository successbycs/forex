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
The entry operation returns `OPEN_MONITORING`; its raw response remains
unchanged. Capture polls only the fixed read-only PostgreSQL lifecycle summary
for up to 15 minutes and retains each observation separately, then binds the
exact accepted proposal and attempt to `CLOSED_MATCHED` broker history. It
never retries an entry. An observation timeout leaves the existing position
monitor responsible for closure and does not establish proof.

The verifier rejects a non-Demo server, Live reference, stale evidence,
changed artifact, mismatched snapshot/owner/position, missing terminal closure,
or incomplete reconciliation. It recomputes broker opening/closing volume,
prices, costs, and AUD P&L. The final broker exit must occur no later than the
submission time plus the existing owner's configured maximum holding period
(6, 8, or 10 minutes), with a matching recorded owner exit reason. A later
broker fill fails the literal close-by-cutoff contract; capture's 15-minute
observation window does not extend the trading cutoff.

Local review on 2026-09-16 repaired an asynchronous-result mismatch, an exact
proposal selection defect, a manifest/registry surface mismatch, and pytest
summary suppression. Focused synthetic tests exercise the complete offline
bundle plus refusal, identity, cutoff, provenance, and integrity failures.
These tests validate tooling, not the real broker surface.

No M30 real-world evidence has been captured yet.
