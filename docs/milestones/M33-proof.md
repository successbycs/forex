# M33 — Demo commission-adjusted P&L comparison proof

M33 is a Demo-only reporting feature. It does not change an MT5 order, risk
limit, account setting, terminal setting, strategy, or any open position.

For an eligible closed, reconciled listener-attributed EUR/USD Demo trade, the
terminal shows the unchanged `Actual broker P&L` and a separate
`Commission-adjusted Demo P&L — GO Plus+ AUD assumption`. The first profile is
explicitly `GO_PLUS_AUD_V1`, an **assumed** AUD 3.00 per side per standard lot.
At 0.01 lots that is AUD -0.03 per side and AUD -0.06 round trip. It is a
counterfactual comparison, not a claim about the current Demo account terms or
a real Live result.

From a clean committed checkout, collect fresh evidence without overwriting an
existing bundle:

    bash scripts/capture_m33_evidence.sh --bundle runs/evidence/M33/<new-directory>
    bash scripts/verify_m33_evidence.sh runs/evidence/M33/<new-directory>

The collector runs only fixed PostgreSQL preflight, verification, projection
and lifecycle operations, then renders the latest day that has an eligible
projection. It retains raw command envelopes, the exact terminal output,
revision, configuration fingerprint and hashes. The verifier performs no
remote access or mutation. `FOREX_M33_PRO_FORMA_COMMISSION_OK` means the
current 24-hour evidence proves the declared reporting surface only. Independent
review and Chris's formal closeout decision remain required.
