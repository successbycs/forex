# Definition of done

A milestone is done only when `forex-milestones prove` writes `proven_at` after confirming:

- dependencies remain `PROVEN`;
- every acceptance criterion has a linked passing observation;
- required artifacts are non-empty;
- milestone and repository verification pass;
- evidence came from the declared real-world surface;
- raw artifacts, exit codes, timestamps, hashes, Git revision, configuration fingerprint, and configured local-runner signature verify under the declared `SELF_ATTESTED_INTEGRITY` tier;
- evidence is fresh and the completion worktree is clean and committed;
- no critical safety, security, integrity, or lookahead blocker remains;
- at M16, M27, and M32 only, four isolated, bound Review Board reviews produce a current deterministic `RECOMMEND_COMPLETE` result;
- every review gate declared by the active contract is satisfied; M20 requires a current Triad-plus-domain recommendation but no human sign-off.

Implementation, tests, documentation, mocks, a generated proof document, `target_date`, and `implementation_finished_at` are not completion. Material change sets a proven milestone to `NEEDS_REVALIDATION` while retaining history.
