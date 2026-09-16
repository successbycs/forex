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

Chris authorised closeout using the retained 15 September drill and approved
its inputs and outputs on 16 September. The registry's M29-only
`retained_evidence_policy` pins
`runs/evidence/M29/20260915T111605Z/manifest.json` with SHA-256
`bd19c0179122cbef432871380837572dddc056067456aea231fd02099dc26785`.
The normal milestone evidence validator checks every artifact, the held/flat
Demo recovery observations, four runtime payload hashes and the governed
configuration. It does not recapture the drill or run the later verifier that
incorrectly requires the collector and runtime revisions to be identical.

The drill runtime revision is `4dc94fe7895fd1a2eee605461a646c9618b29c1a`,
the later diagnostics report `4fc956d5184d4f0c3a47c7d3c469fac9ff2843e8`,
and the collector revision is `7a2fd92690203019ad57349d4f2bf633f93b93e6`.
All four runtime payload hashes and the governed configuration agree. These
are retained provenance facts; no capture is relabelled as a newer release.

For this exact bundle, elapsed age and documentation or evidence-tool changes
do not erase the observed function result. Runtime payload/configuration or
recovery-surface changes and evidence tampering invalidate its acceptance.
Current local verification and a clean implementation worktree remain required.
Chris's recorded approval stays bound to the same manifest and configuration;
a later local verification does not demand another approval of identical raw
inputs and outputs. Other milestones retain their existing gates.

This does not claim an upstream broker outage, durable collection
deduplication, profitability, or Live capability. Those are deliberately
outside the MVP M29 contract.
