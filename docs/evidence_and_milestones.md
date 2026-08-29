# Evidence-gated milestone execution

`milestone_registry.json` is the human-readable, declarative transition-contract registry. It contains scope, dependencies, acceptance criteria, fixed verification commands, the claimed real-world surface, proof freshness, invalidation triggers, and optional human-owned target dates. It must not contain mutable status or completion claims.

`project_state.json` is mutable execution state. `runs/run_history.json` is the append-only logical audit history written by the CLI. Raw verification output and proof bundles are deliberately ignored by Git because they can contain machine-local observations; retain or export them under the operator's evidence policy.

## Evidence assurance tier

Every milestone currently declares `SELF_ATTESTED_INTEGRITY`. M0 uses a fixed-job local evidence runner that signs the manifest digest using a private key kept outside Git; the repository verifies it with the stored public key. M1's approved MVP bridge instead retains hash-addressed raw capture, verification, and repository-verification outputs, bound to the repository revision and governed configuration. M1 deliberately does not authenticate the remote probe bytes or its machine-local interpreter. Neither pattern is an external witness or separately controlled identity. This does not weaken the Demo-only repository boundary, human approval, Triad review, or prohibition on live trading.

## Three-phase operating model

The registry divides the route into historical foundation (M0–M16), offline decision and safety controls (M17–M26), and real-time Demo operations (M27–M32). Closed historical bars are valid evidence for the historical and replay contracts only. They cannot satisfy a fresh-tick, current-spread, live-market recovery, or Demo-execution contract. Real-time validation uses `GOMarketsMU-Demo` only; `GOMarketsMU-Live` remains prohibited.

## What completion means

Implementation, tests, evidence capture, verification, and approval are distinct events. A milestone is complete only when `forex-milestones prove --id Mx` successfully writes `proven_at`. The command refuses closeout unless dependencies, all acceptance checks, required artifacts, fixed verification commands, current real-world evidence, configuration/revision matching, blockers, and any required human sign-off all pass.

`target_date` is an editable planning forecast owned by the human operator. It never causes closeout and is never reported as the actual completion date. A material change moves previously proven work to `NEEDS_REVALIDATION`; `first_proven_at` remains historical while a fresh `proven_at` is generated after revalidation.

## Normal execution

```text
python3 scripts/forex_milestones.py validate
python3 scripts/forex_milestones.py show --id M0
python3 scripts/forex_milestones.py start --id M0
# implement only M0
python3 scripts/forex_milestones.py record-check --id M0 --criterion M0-C1 --result PASS --evidence <path> --note <observation>
python3 scripts/forex_milestones.py verify --id M0
bash scripts/capture_m0_evidence.sh
python3 scripts/forex_milestones.py record-evidence --id M0 --manifest runs/evidence/M0/<run>/manifest.json
python3 scripts/forex_milestones.py finish-implementation --id M0
```

If human review is required, the human operator reviews the declared inputs, outputs, raw evidence, deferred scope, and safety boundaries. Their explicit decision can then be recorded:

```text
python3 scripts/forex_milestones.py signoff --id M0 --operator <identity> --decision approve --note <review-note> --confirm-inputs-reviewed --confirm-outputs-reviewed
python3 scripts/forex_milestones.py prove --id M0
```

Do not record approval on someone else's behalf. `prove` prepares `M1` as `READY` but never starts it.

## Failure and drift

- Use `block` for a missing external surface or dependency.
- Use `needs-fix` after a failed implementation or verification result.
- Use `invalidate` when a proven capability's implementation, dependency, surface, schema, or governed configuration materially changes.
- `refresh-fingerprint` acknowledges current operator configuration but proves nothing. Re-run affected verification and real-world proof after a material change.

Evidence capture and evidence verification are separate. The verifier does not contact, modify, repair, or regenerate the observed system. Hash, freshness, revision, surface, configuration, runner-attestation, and signature mismatches fail closed. Its independence is logical separation within the repository, not a separate provenance authority.

## Durable evidence export

Raw bundles and review submissions are ignored by Git to avoid publishing machine-local observations. Export the latest verified bundle, recorded Triad cycle, registry, state, and run history to an operator-selected retained location:

```bash
python3 scripts/forex_milestones.py export-evidence --id M0 --destination /path/to/retained/evidence
cd /path/to/retained/evidence
sha256sum --check forex-M0-evidence-<timestamp>.tar.gz.sha256
```

The destination must be protected according to the sensitivity of later milestone evidence. Export does not close or approve a milestone.
