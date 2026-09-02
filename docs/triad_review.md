# Review Board: Triad plus domain assurance

The Triad review consists of three engineering lenses plus a Forex domain lens:

- AI Engineer
- Solution Architect
- Senior Software Developer
- Financial and Quantitative Research Analyst

These reviewers provide isolated recommendations; they are not completion authorities. Real-world evidence and deterministic verification must already pass. The human operator remains the only final decision-maker.

Reviewers assess evidence against the milestone's declared `SELF_ATTESTED_INTEGRITY` tier and its milestone-specific evidence requirements. M0 requires its local runner signature. M1's approved MVP bridge instead requires retained, hash-addressed raw capture, verification, and repository-verification outputs bound to the repository revision and governed configuration; it deliberately does not authenticate the remote probe bytes or machine-local interpreter. The absence of an external witness, separate signing identity, or M1 remote-executable identity is a documented limitation, not by itself a contract failure.

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

## When it is required

The Review Board is a phase-gate check, not a per-milestone development gate.
It is required only for M16, M27, and M32. A human may request it for another
milestone when the change is unusually consequential, but it is otherwise not
part of normal MVP implementation or closeout.

## Workflow

### Mandatory automated execution and retry

Before every milestone `prove`, prepare and submit one exact current packet to
each of the four roles. Validate and record each response automatically. A
request, response, schema, or recording failure is retryable: diagnose the raw
error, apply only the smallest MVP-compatible correction, and resubmit the
affected role immediately. Limit one root cause to three attempts.

After the third failed attempt, retain the raw failure and record its cause.
Run a focused Board assessment of the review-workflow failure where possible.
Only when the milestone's implementation, tests, T480 evidence, evidence
verification, and safety boundaries are complete may delegated operator
authority record an MVP exception. That exception applies only to review
automation; it never invents reviewer identities, findings, evidence, passing
checks, or approval.

After committed-revision evidence is recorded for a required phase gate or a
human-requested review:

```bash
python3 scripts/forex_triad.py prepare --id <milestone>
```

For normal automated execution, use the bounded runner instead. It launches
fresh read-only Codex CLI sessions one role at a time, retains every raw
attempt, validates an accepted response unchanged, and retries only the failed
role up to three times:

```bash
python3 scripts/run_triad_reviews.py --id <milestone> --record-recommendation
```

The command creates `runs/triad/<milestone>/<cycle>/` with a request, four role packets, four JSON templates, and an empty submissions directory. Give each packet to a separate read-only review session. Do not show any reviewer another submission before its verdict is saved.

Place completed reviews under `submissions/` using the generated role filenames, then validate and synthesize:

```bash
python3 scripts/forex_triad.py validate-review --cycle <cycle> --review <review.json>
python3 scripts/forex_triad.py recommend --cycle <cycle>
python3 scripts/forex_triad.py assess --recommendation <cycle>/recommendation.json
```

Every required Review Board iteration must produce a new review cycle. The deterministic synthesizer writes both the machine-readable `recommendation.json` and the required human-readable `review-summary.md` for that cycle. The summary clearly states whether the board supports completion, shows every reviewer's position, lists blockers and observations, and says whether human approval is currently eligible. The board provides a recommendation only; the human remains the approval authority.

The summary filename is operator-configurable in `config/triad.yaml`. It is mandatory: recording, human sign-off and milestone closeout fail if the summary is missing, modified, stale, or no longer matches its recommendation. A remediation iteration requires fresh evidence where affected and a completely new isolated review cycle; an earlier summary cannot be reused.

Regenerate the human-readable summary from an existing recommendation when required:

```bash
python3 scripts/forex_triad.py summary --recommendation <cycle>/recommendation.json
```

The synthesizer returns `DO_NOT_COMPLETE` when any required review is missing or invalid, a required role returns `FAIL` or `ABSTAIN`, an assigned criterion is not passed, reviewer sessions are reused, a binding has drifted, or an open critical/high finding exists. Otherwise it returns `RECOMMEND_COMPLETE`, retaining lower-severity observations for the human.

Record only a healthy completion recommendation:

```bash
python3 scripts/forex_milestones.py record-triad-recommendation \
  --id <milestone> --recommendation <cycle>/recommendation.json
```

Recording automatically passes the Triad acceptance criterion. Any later change to the commit, configuration, evidence, verifier, milestone contract, review request, or recommendation invalidates the gate.

## Human decision

The Triad recommendation answers whether the reviewed evidence supports milestone completion. It does not close the milestone. The human reviews disagreements, observations, limitations and raw proof, then explicitly approves or rejects. `proven_at` remains available only after the human gate passes.

There is no mandatory pre-implementation Review Board. Build normally, keep
the fixed safety boundaries, and reserve the board for the three phase gates
or a human-requested decision.
