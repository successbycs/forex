# Ancillary governance implementation workstream

## Purpose and boundary

This workstream improves the Builder → fresh Reviewer → human acceptance
handoff for repository development. It is not a Forex trading/research
capability and is outside the `M0`–`M32` delivery roadmap.

`milestone_registry.json`, `project_state.json`, `runs/run_history.json`,
`runs/evidence/`, and `runs/triad/` remain authoritative for Forex milestones.
The work packages below are a human-owned implementation plan; they do not
have `proven_at`, cannot unlock a Forex milestone, and cannot close one.

## Operating rules

- Start a package only with explicit human authorisation.
- Preserve the active Forex milestone and do not modify its state merely to
  demonstrate this workstream.
- A separate Codex session is fresh logical review context, not independent
  execution provenance or an external identity.
- Reviewers are read-only and never sign off, prove, commit, deploy, mutate
  data, or claim completion.
- Builder remediation after review requires a fresh human instruction.
- No background watcher, autonomous fix loop, new database, external workflow
  engine, or public service is in scope.
- Every implementation change remains subject to `AGENTS.md`, including the
  explicit-human-approval rule for commits and consequential actions.

## Work-package map

```text
GW0 Scope and design review
 └─ GW1 Durable role guides
     └─ GW2 Bound request/result format
         └─ GW3 Existing-governance integration
             └─ GW4 Test-only dummy workflow
                 └─ GW5 Human-operated dual-session trial
                     └─ GW6 Bounded review dispatcher
```

## Packages

### GW0 — Scope and design review

**Initial status:** `PLANNED`  
**Depends on:** none

Define the minimum design that reuses the current milestone, evidence, and
Triad mechanisms. Confirm it does not create a second state machine or weaken
human authority.

**Acceptance conditions:**

- Existing handoff fields and events are explicitly mapped.
- The design identifies the active Forex milestone boundary and the required
  human authority before any implementation.
- The design distinguishes fresh logical review context from independent
  provenance.

### GW1 — Durable Builder and Reviewer role guides

**Initial status:** `PLANNED`  
**Depends on:** GW0

Add concise `builder.md`, `reviewer.md`, and workflow guidance under this
directory. They reference existing repository authority rather than duplicating
it.

**Acceptance conditions:**

- Builder scope, prohibited actions, required inputs, and review-request
  output are explicit.
- Reviewer is explicitly read-only and can return only `CHANGES_REQUIRED`,
  `BLOCKED`, or `RECOMMEND_COMPLETE`.
- Human sign-off and `prove` remain the only route to `PROVEN`.

### GW2 — Bound review request and result format

**Initial status:** `PLANNED`  
**Depends on:** GW1

Define machine-readable, schema-validated review request and result records.
They bind a review to the exact contract, Git revision, configuration
fingerprint, verification outputs, evidence manifest where applicable, and
review cycle.

**Acceptance conditions:**

- Mismatched milestone, revision, fingerprint, contract, request ID, or cycle
  is rejected.
- Records are immutable inputs to the existing Triad process.
- No reviewer result can approve, sign off, or prove a milestone.

### GW3 — Existing-governance integration

**Initial status:** `PLANNED`  
**Depends on:** GW2

Add the smallest possible request/record commands and metadata. Do not add new
primary milestone statuses.

**Required trigger rules:**

```text
Builder → Reviewer requires:
- current active milestone;
- status IN_PROGRESS;
- implementation_finished_at present;
- verification.passed true;
- verification revision/fingerprint current;
- no unresolved blockers;
- no duplicate request for the same binding;
- fewer than three cycles.

CHANGES_REQUIRED → NEEDS_FIX with a blocker containing request and finding IDs.
RECOMMEND_COMPLETE → existing Triad recording only; stop for human sign-off.
```

**Acceptance conditions:**

- Existing `IN_PROGRESS`, `NEEDS_FIX`, Triad, sign-off, and `PROVEN` semantics
  remain unchanged.
- Request/result events are appended to `runs/run_history.json`.
- No automatic Builder launch, commit, deployment, database mutation, sign-off,
  or closeout exists.

### GW4 — Test-only dummy workflow

**Initial status:** `PLANNED`  
**Depends on:** GW3

Run the new handoff on a temporary copied governance fixture, for example
`GW-TEST-001`, rather than on a real Forex milestone.

**Acceptance conditions:**

- Demonstrates `IN_PROGRESS → review request → CHANGES_REQUIRED → NEEDS_FIX →
  remediation → fresh review request → RECOMMEND_COMPLETE`.
- Demonstrates cycle four is rejected.
- Demonstrates a reviewer cannot self-approve, sign off, or prove.
- Does not write `proven_at`, real-world evidence, or mutable state for M0–M32.

### GW5 — Human-operated dual-session trial

**Initial status:** `PLANNED`  
**Depends on:** GW4

The human opens a separate read-only Reviewer Codex/VS Code context, preferably
at a detached worktree for the Builder's reviewed commit. The Builder-side
recorder validates the structured result.

**Acceptance conditions:**

- Reviewer has no write authority in the Builder worktree.
- Request/result binding validates end-to-end.
- The human confirms the review/fix flow is understandable and safe.
- No actual Forex milestone is adopted or closed without a separate explicit
  human instruction.

### GW6 — Bounded review dispatcher

**Initial status:** `PLANNED`  
**Depends on:** GW5

Implement a human-invoked, one-shot reviewer dispatcher. It is an orchestration
helper, not a background service or autonomous agent loop.

**Acceptance conditions:**

- One human command launches at most one fresh read-only review context.
- It stops on failed execution, unexpected state, `BLOCKED`, uncertainty, or
  three cycles.
- It cannot launch remediation, commit, deploy, mutate a database, sign off,
  prove, or close a milestone.

## Adoption gate

Only after GW4 and GW5 have passed may the human explicitly decide whether to
adopt this workflow for an active Forex milestone. Adoption is a separate
decision from implementing or testing the workstream.
