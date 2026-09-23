# M31 retained-evaluation repair review

Implementer: `/root`. Independent read-only reviewer: `/root/m31_gap_review`.
This record transcribes the separate review; it is not a Triad completion
recommendation or human approval.

The reviewer found no blocking implementation issue for committing and
capturing the retained-evidence evaluation. It independently ran 33 M31 tests,
all passing. The implementer's wider focused run passed 60 tests covering M31,
the bounded adapter, completeness parsing and broker-history reporting.

Reviewed SHA-256 identities:

- `scripts/m31_retained_evidence.py`:
  `cb1bf30aab53910e45fe7495c5335c3831712a7f7e05b0ece8b0bf5f94d09fdd`.
- `src/forex/m31_supplement.py`:
  `bd7df1145a6b1806fd9b197d59ab4610a76f1b38057b3348f61199463f01203a`.

Required repairs verified: original manifest digest validation; equality of all
original decision fields; Demo/EURUSD/M1 session scope; a single strategy
version; runtime and configuration provenance; actual historical session count;
and broker zero-deal cross-check for the same interval. The formal wrapper
checks committed evaluator/configuration identity, clean material worktree,
observation freshness, retained test/governance receipts and deterministic
recomputation.

The reviewer accepted the historical null-policy comparison as defensible
within the predeclared NO_CHANGE scope without a new operator scope decision.
It requires these limits to remain explicit: exact historical artifact bound
after observation; no direct proposal/account hash join; no active-strategy
performance result; no assessment of existing positions or floating P&L.

Non-blocking clarity suggestion: the scorecard's “Evaluation incomplete” line
could distinguish technical evaluation from formal approval. The formal wrapper
already adds an explicit technical-proof versus closeout explanation.

Remaining: actual clean-revision capture/verification and required bound
completion recommendation, then human signoff. No broker changes were made.

## Bound-review repair: SSD-M31-001

The first formal cycle `M31-20260923T022714Z-25e1b591` found a HIGH gap:
the review fingerprint included the shell verifier but omitted its dispatched
Python implementations. That cycle cannot support completion.

The M31-only `_verifier_paths` selection in `src/forex/triad.py` now explicitly
includes both dispatch branches and local validation dependencies. A regression
test changes each copied dependency and requires a changed review fingerprint.
The capture receipt now also runs `tests/test_triad.py`.

Independent reviewer `/root/m31_gap_review` accepted this repair and ran all
eight Triad tests successfully. The full focused run passed 68 tests. A fresh
committed M31 evidence/review binding is required; the original observation and
M30 runtime proof do not need repeating. No runtime behavior was changed.
