# Triad plus domain milestone assurance

The Triad review consists of three engineering lenses plus a Forex domain lens:

- AI Engineer
- Solution Architect
- Senior Software Developer
- Financial and Quantitative Research Analyst

These reviewers provide isolated recommendations; they are not completion authorities. Real-world evidence and deterministic verification must already pass. The human operator remains the only final decision-maker.

## Trust and independence boundary

Each role receives a separate immutable review packet and must review read-only without seeing another role's verdict. The packet binds the review to:

- milestone contract hash;
- Git revision;
- effective governed-configuration fingerprint;
- evidence-manifest hash;
- verifier fingerprint;
- role-prompt hash;
- review-cycle request hash.

AI personas—even separate sessions—are not fully independent organisations. Isolation reduces anchoring and makes disagreements visible; it does not replace human judgment or external-system proof.

## Workflow

After committed-revision evidence is recorded:

```bash
python3 scripts/forex_triad.py prepare --id M0
```

The command creates `runs/triad/M0/<cycle>/` with a request, four role packets, four JSON templates, and an empty submissions directory. Give each packet to a separate read-only review session. Do not show any reviewer another submission before its verdict is saved.

Place completed reviews under `submissions/` using the generated role filenames, then validate and synthesize:

```bash
python3 scripts/forex_triad.py validate-review --cycle <cycle> --review <review.json>
python3 scripts/forex_triad.py recommend --cycle <cycle>
python3 scripts/forex_triad.py assess --recommendation <cycle>/recommendation.json
```

The deterministic synthesizer returns `DO_NOT_COMPLETE` when any required review is missing or invalid, a required role returns `FAIL` or `ABSTAIN`, an assigned criterion is not passed, reviewer sessions are reused, a binding has drifted, or an open critical/high finding exists. Otherwise it returns `RECOMMEND_COMPLETE`, retaining lower-severity observations for the human.

Record only a healthy completion recommendation:

```bash
python3 scripts/forex_milestones.py record-triad-recommendation \
  --id M0 --recommendation <cycle>/recommendation.json
```

Recording automatically passes the Triad acceptance criterion. Any later change to the commit, configuration, evidence, verifier, milestone contract, review request, or recommendation invalidates the gate.

## Human decision

The Triad recommendation answers whether the reviewed evidence supports milestone completion. It does not close the milestone. The human reviews disagreements, observations, limitations and raw proof, then explicitly approves or rejects. `proven_at` remains available only after the human gate passes.

## Pre-implementation use from M1 onward

Before implementation, the same roles should challenge the proposed contract and verifier. After implementation, new isolated sessions review the real proof. This temporal separation prevents Codex from silently redefining success after observing its own result.
