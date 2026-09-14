
# Project overview
To build an end to end solution to trade Forex autonomously and provide a positive return over time.  To use external economic data to support trade or no trade decisions.

# Project Structure
Use HArness engineering to set-up this repo and to strucuture files, capabilities and features as per this link. https://openai.com/index/harness-engineering/

# Architecture
Use https://matklad.github.io/2021/02/06/ARCHITECTURE.md.html as a guide to Architecture.md  Examples of Architecture.md are. https://github.com/rust-lang/rust-analyzer/blob/d7c99931d05e3723d878bea5dc26766791fa4e69/docs/dev/architecture.md  

# Execution Plans
Use this link as the base knowledge: https://developers.openai.com/cookbook/articles/codex_exec_plans


# Build and test
Once a piece of function has been built it must be tested and include a real world outcome.  The build must move the project forward and any code change must move the project towards its goal of autonomoud Forex execution.#


# Forex agent operating rules

- Inspect `git status` before editing and preserve unrelated work.
- Read `project_state.json`, the active contract in `milestone_registry.json`, and `docs/evidence_and_milestones.md` before milestone work.
- Implement only the active milestone. Do not automatically begin the next milestone.  Begin the next milestone if there is a Goal defined that defines this.
- Treat `target_date` as a human-owned forecast. Only the closeout command may generate the actual completion timestamp, `proven_at`.
- Never claim completion from code, tests, mocks, documentation, or narrative JSON alone. Capture and independently verify proof on the contract's declared real-world surface.
- Require a current Triad-plus-domain `RECOMMEND_COMPLETE` result bound to the exact contract, revision, configuration, verifier, and evidence. Review roles are read-only and cannot approve or close milestones.
- Keep raw evidence separate from verification results. Never fabricate, repair, or overwrite captured evidence.
- Put changeable non-secret operator settings in canonical configuration files. Put secrets and machine-local values in ignored environment or local override files.
- A material implementation, dependency, schema, surface, or governed-configuration change invalidates affected proof.
- Shared platform transport belongs to `cs-ai-lab-infra`; Forex owns its adapter catalog, application schemas, workflows, and evidence.
- Preserve the hard safety boundary: no trading on `GOMarketsMU-Live`, 
- Trading on `GOMarketsMU-Demo`is approved by Chris the human operator
- Do not commit, push, create a branch, or open a pull request without explicit human instruction.

## Active delivery direction — Harness H1–H4

For autonomous-delivery planning, the active non-formal sequence is **Harness
H1–H4 → Wave A → Wave B → Wave C**. It does not alter `project_state.json`,
the active M29 contract, broker authority, or proof gates. H_SLOW and broader
research remain retained but deferred unless Chris explicitly reactivates them.

Every bounded task records its owned paths, acceptance checks and actual test
or observation result; raw evidence remains distinct from verification and
formal proof. Terra receives one bounded implementation package. Astra reviews
each result. After two failed Terra repair attempts on the same defect, Astra
owns the repair; an independent read-only reviewer checks Astra's material fix.
Neither workflow status nor tests may be represented as real-world proof.

The repository instructions require a current Triad-plus-domain recommendation
for closeout, while every formal closeout must also obey its exact registry
contract. Until Chris reconciles any narrower contract wording, apply the
stricter combined requirement; do not waive either rule by delivery planning.
