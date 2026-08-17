# Forex agent operating rules

- Inspect `git status` before editing and preserve unrelated work.
- Read `project_state.json`, the active contract in `milestone_registry.json`, and `docs/evidence_and_milestones.md` before milestone work.
- Implement only the active milestone. Do not automatically begin the next milestone.
- Treat `target_date` as a human-owned forecast. Only the closeout command may generate the actual completion timestamp, `proven_at`.
- Never claim completion from code, tests, mocks, documentation, or narrative JSON alone. Capture and independently verify proof on the contract's declared real-world surface.
- Keep raw evidence separate from verification results. Never fabricate, repair, or overwrite captured evidence.
- Put changeable non-secret operator settings in canonical configuration files. Put secrets and machine-local values in ignored environment or local override files.
- A material implementation, dependency, schema, surface, or governed-configuration change invalidates affected proof.
- Shared platform transport belongs to `cs-ai-lab-infra`; Forex owns its adapter catalog, application schemas, workflows, and evidence.
- Preserve the hard safety boundary: no live trading, no `GOMarketsMU-Live`, no agent execution authority, and no order surface before M27.
- Do not commit, push, create a branch, or open a pull request without explicit human instruction.
