# M29 proof

M29 is the lean Demo-MVP listener-recovery gate. Its real-world surface is the
permanent `GOMarketsMU-Demo` EURUSD listener under maintenance hold. A valid
run records an initially flat AUD Demo account, a controlled listener-worker
handoff, recovery of the same release-bound S4U task, and a flat held account
afterward. It cannot assess or place an order while the hold is active.

`scripts/capture_m29_evidence.sh` retains raw fixed-operation envelopes and
the release, revision, configuration and event-log bindings. The offline
verifier checks those retained bytes only; it does not contact T480 or MT5.
The required success marker is `FOREX_M29_PROOF_OK`.

This does not claim an upstream broker outage, durable collection
deduplication, profitability, or Live capability. Those are deliberately
outside the MVP M29 contract.
