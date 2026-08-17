# M0 human closeout guide

M0.1–M0.4 are implementation and proof work packages. M0.5 is the isolated Triad-plus-domain assurance review. M0.6 is deliberately reserved for the human operator.

## Review before authorizing a commit

Inspect:

- `git status --short` and the complete proposed diff;
- `milestone_registry.json`, especially M0 scope, M1 boundary, and all 21 criteria;
- `python3 scripts/t480_adapter.py dependency-status`, which must report `ok: true` for a clean, tracked, revision- and hash-matched shared core;
- `config/*.yaml` and the hard safety constraints;
- `docs/architecture.md`, `docs/security_model.md`, and deferred capabilities;
- the latest `runs/evidence/M0/<run>/manifest.json` and raw outputs;
- `python3 scripts/forex_milestones.py work-packages --id M0`;
- `python3 scripts/forex_milestones.py prove --id M0`, which must still refuse closeout.

If the implementation is acceptable, explicitly authorize the agent to create the M0 implementation commit. A commit is required because an unborn or materially dirty source tree cannot provide immutable proof attribution.

## Proof from the committed source revision

After the implementation commit, the agent should:

1. Run milestone and repository verification.
2. Capture a fresh isolated-environment bundle.
3. Run the independent verifier and all black-box negative controls, including stale, dirty, revision/configuration drift, missing marker, altered exit code, missing artifact, and path escape.
4. Record the fresh evidence and acceptance observations.
5. Export the evidence to the operator-selected retained location, if supplied.
6. Prepare four immutable role packets and obtain isolated, read-only reviews.
7. Synthesize and record the bound recommendation.
8. Present the exact Git revision, configuration fingerprint, evidence manifest hash, verifier fingerprint, review verdicts, findings, test count, limitations, and closeout errors.

The operator then explicitly approves or rejects the current inputs and outputs. Approval must identify the operator and include a review note. Only after approval may the agent record M0-C19, verify M0.6, and run `prove`.

Successful `prove` generates `proven_at`, sets M1 to `READY`, and stops. It does not start M1.
