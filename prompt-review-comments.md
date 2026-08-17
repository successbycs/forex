# Forex foundation prompt — review comments

Review date: 2026-08-17

This review did not execute the Forex foundation prompt and did not modify either reference repository.

## Sources inspected

- `successbycs/Autonomous-Framework`, current `main` commit `174226df` dated 2026-04-25.
- `successbycs/SuccessByCS-Builder`, current `main` commit `a098bde` dated 2026-04-03. Its Autonomous Framework gitlink points to the older framework commit `6035d544`; the current Autonomous Framework repository was therefore inspected directly.
- Local `successbycs/cs-ai-lab-infra`, current `main` commit `e11c27d` dated 2026-08-13.
- The AI Lab checkout contains pre-existing uncommitted edits to `t480/milestone-registry.json` and `t480/milestones.md`, plus Python cache directories. They were inspected but not changed.

## Findings incorporated into the rewrite

### 1. A milestone should be a transition contract

The strongest Autonomous Framework convention is that a milestone is not merely a prompt or task list. It declares a bounded state transition:

- what must already be true
- what will become true
- which execution surface is allowed
- which artifacts must exist
- what observable evidence proves the outcome
- which state follows success

The rewritten prompt adopts this structure without copying the Autonomous Framework's multi-agent controller hierarchy.

### 2. Completion must mean proven, not implemented

The AI Lab milestone tool uses `proven` and writes `proven_at` only after all required checks pass. Its registry also rejects any milestone that lacks a `real_world_execution` check. This is better than allowing documentation, tests, or a self-authored JSON file to establish completion.

The rewritten prompt therefore distinguishes:

- implementation finished
- automated verification passed
- real-world proof captured
- human approval recorded, where required
- milestone proven

`proven_at` is the authoritative completion timestamp. It is written in UTC by the closeout command only after all gates pass. An agent must not manually choose or predict a completion date.

### 3. Raw evidence and verification should be separate

The AI Lab's M2 and M3 proof flows capture raw evidence on the actual T480 and then verify the retained bundle independently. Useful elements include:

- capture timestamp
- Git revision
- execution host or role
- raw command output
- exit status
- expected result
- SHA-256 manifest
- a verifier that does not contact or mutate the live system

The rewritten prompt uses the same principle. A polished proof JSON can index evidence, but cannot replace raw observed evidence.

### 4. Proof must match the claimed surface

The Autonomous Framework's own proof-value audit found many completed milestones supported only by low-value JSON or narrative artifacts. Its later definition of done corrected this by requiring human-observable runtime evidence.

Forex should avoid the same failure mode from its first milestone. Examples:

- An MT5 milestone requires evidence from the installed Windows MT5 terminal.
- A WSL integration milestone requires a request that crosses the actual Windows/WSL boundary.
- A PostgreSQL milestone requires a real write/read round trip against the selected isolated Forex database or schema.
- A recovery milestone requires an actual isolated recovery drill.
- A strategy milestone requires point-in-time replay and out-of-sample results, not indicator unit tests alone.
- A demo execution milestone requires a broker-confirmed demo operation and reconciliation.

### 5. Configuration drift must be controlled

The recent AI Lab state provides a concrete example: Compose is pinned to n8n `1.123.65`, while the committed M2 evidence verifier still expects `1.118.1`. The current uncommitted M6 edits explicitly add work to correct that stale expectation.

This demonstrates why changeable values should not be duplicated through code, docs, verification scripts, and milestones. The rewritten prompt introduces:

- version-controlled, non-secret operator configuration
- local secret/host overrides excluded from Git
- typed configuration validation
- a configuration fingerprint in evidence bundles
- verification code that reads canonical configuration rather than repeating values
- tests that fail when configuration and verification expectations diverge

Safety invariants are an exception. Live trading prohibition, risk authority, approval requirements, and absence of order endpoints before their milestone must be enforced in code and architecture, not weakened into casually editable settings.

### 6. M0 should remain small

The original prompt asked M0 to create a large documentation library and a 31-milestone registry while also warning against horizontal architecture. The rewrite reduces M0 to the minimum operating foundation and defers specialist documents and configuration files until their capabilities exist.

### 7. The project name and purpose needed correction

The project is now `Forex`. `$10ADay` is not used as the application name.

Approximately USD 10 per trading day or USD 300 per month is retained only as a distant, aspirational research benchmark. It is not a requirement, sizing input, daily quota, acceptance criterion, or reason to manufacture trades.

The primary objective is learning. The intended maturity path is:

```text
research and education
-> observable decision support
-> human-approved trading assistance
-> possible demo automation
-> possible future live-readiness assessment
```

No stage is guaranteed to advance to the next.

### 8. Backtesting was missing from the milestone path

The original architecture described backtesting but did not include a dedicated deterministic backtesting and walk-forward milestone before demo execution. The rewrite adds one before agent authority, risk approval, or execution work.

### 9. Agent authority should begin in shadow mode

"Observer/adviser" was open to interpretation. The rewrite defines explicit modes and starts with `SHADOW`: the agent's recommendation is logged and evaluated but cannot create, modify, approve, reject, size, or execute a trade.

### 10. Persistent Codex rules need a repository entry point

The rewrite requires a concise root `AGENTS.md`. Detailed governance stays in documentation, while the rules future sessions must discover automatically remain short and authoritative.

## Recommended milestone state model

Use these states:

- `PLANNED`
- `READY`
- `IN_PROGRESS`
- `BLOCKED`
- `NEEDS_FIX`
- `AWAITING_REAL_WORLD_PROOF`
- `AWAITING_HUMAN_SIGNOFF`
- `PROVEN`
- `NEEDS_REVALIDATION`
- `SUPERSEDED`

Important timestamps:

- `started_at`
- `implementation_finished_at`
- `verification_passed_at`
- `real_world_proof_captured_at`
- `human_signed_off_at`
- `first_proven_at`
- `proven_at`
- `last_validated_at`

Only `proven_at` means the milestone completed. If a material input, implementation surface, dependency, or canonical configuration changes, the milestone should move to `NEEDS_REVALIDATION`; historical proof timestamps remain in the audit trail.

If planning dates are useful, store an optional human-owned `target_date` separately. A target is a forecast, can be changed through configuration or planning state, and must never be presented as the actual completion date. The actual date remains the system-generated `proven_at`.

## Configuration recommendation

Use YAML for human-edited non-secret settings, JSON Schema or typed application models for validation, and environment variables for secrets and machine-local addresses.

For the bootstrap T480 transport, JSON is also appropriate because the adapter
must validate before the full application dependency set exists. It should not
duplicate values later introduced in YAML.

Start with only the files M0 and M1 need:

```text
config/
  project.yaml
  runtime.yaml
  mt5.yaml
  market_data.yaml
  logging.yaml
  schemas/
```

Add `database.yaml`, `models.yaml`, `agent.yaml`, `risk.yaml`, `execution.yaml`, and notification configuration only with the milestone that introduces each capability.

Configuration files should contain values expected to vary. Fixed safety and architectural rules should remain code-enforced and documented as decisions.
