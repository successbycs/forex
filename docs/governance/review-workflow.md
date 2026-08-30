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

To avoid manually composing a final-Triad reviewer prompt, prepare one isolated
role handoff for the active milestone:

```bash
python3 scripts/ptr.py --role solution_architect
```

Use a separate fresh Reviewer Codex session for each role. Paste the emitted
prompt into that session, then copy its JSON-only reply to the precise
`submissions/` path printed in the prompt. For a non-active milestone, provide
`--id M2`. In this prompt-only mode, `ptr.py` neither launches Codex nor saves
a review record, changes milestone state, commits, or invokes any Forex
capability.

For a sequential automated request/response handoff instead, run:

```bash
python3 scripts/ptr.py --id M2 --sequence
```

It opens a new read-only ephemeral Codex context for each missing role, waits
for a JSON-only response, validates it against the immutable packet, records it
only after validation, then requests the next role. It skips already-valid
submissions and stops on the first timeout, malformed reply, or failed review;
it never treats a missing response as a PASS. The command does not recommend,
sign off, prove, or close a milestone.
