# Builder, Reviewer, and human workflow

The repository already has final evidence review through `forex_triad.py`.
This lightweight handoff adds implementation-readiness review before real-world
evidence capture; it does not replace the Triad.

```text
IN_PROGRESS
  → finish implementation
  → AWAITING_REAL_WORLD_PROOF
  → fixed verification passes
  → implementation-readiness request
  → CHANGES_REQUIRED / BLOCKED / READY_FOR_EVIDENCE
  → declared evidence stage
  → existing evidence-bound Triad
  → human sign-off
  → prove
  → PROVEN
```

The handoff command requires the current active milestone, an implementation
finish timestamp, current passing verification, a clean committed worktree, no
open blockers, and fewer than three review cycles. `CHANGES_REQUIRED` maps to
the existing `NEEDS_FIX`; `BLOCKED` maps to the existing `BLOCKED`. The human
must explicitly authorise remediation.

The dispatcher is optional to invoke and always one-shot. It invokes Codex in
read-only sandbox mode with a fixed structured-result schema. It never watches
the repository, launches remediation, commits, deploys, mutates data, signs
off, proves, or closes a milestone.
