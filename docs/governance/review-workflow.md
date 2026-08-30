# Builder, Reviewer, and human workflow

The repository already has final evidence review through `forex_triad.py`.
An extra implementation review is optional, human-invoked advice before
real-world evidence capture; it does not create a new state or gate.

```text
Builder implements and verifies
  → human requests fresh read-only review when useful
  → Builder addresses required findings only when human-authorised
  → declared evidence stage
  → existing evidence-bound Triad
  → human sign-off
  → prove
  → PROVEN
```

The human decides when an extra review is useful, receives its findings, and
explicitly authorises any remediation. Findings may be retained in the Builder
report or existing run history when relevant. Reviewers never sign off, prove,
commit, deploy, mutate data, or close a milestone.

To avoid manually copying a Reviewer prompt, run one fresh read-only review of
the current Builder diff:

```bash
python3 scripts/ptr.py
```

`ptr.py` only starts the review and prints its response. It does not save a
review record, change milestone state, launch a Builder, commit, or invoke any
external Forex capability.
