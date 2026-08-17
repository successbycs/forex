# Definition of done

A milestone is done only when `forex-milestones prove` writes `proven_at` after confirming:

- dependencies remain `PROVEN`;
- every acceptance criterion has a linked passing observation;
- required artifacts are non-empty;
- milestone and repository verification pass;
- evidence came from the declared real-world surface;
- raw artifacts, exit codes, timestamps, hashes, Git revision, and configuration fingerprint verify independently;
- evidence is fresh and the completion worktree is clean and committed;
- no critical safety, security, integrity, or lookahead blocker remains;
- four isolated, bound Triad-plus-domain reviews produce a current deterministic `RECOMMEND_COMPLETE` result;
- required human review is explicitly recorded against the current evidence and verification.

Implementation, tests, documentation, mocks, a generated proof document, `target_date`, and `implementation_finished_at` are not completion. Material change sets a proven milestone to `NEEDS_REVALIDATION` while retaining history.
