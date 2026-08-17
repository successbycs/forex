# AI Engineer review contract

Review evidence integrity, agent and tool authority, evaluation design, leakage, prompt/model provenance, verifier independence, and whether the claimed result can be manufactured by the implementation under review.

Challenge at least:

- whether the proof is bound to immutable code and effective configuration;
- whether capture and verification are truly separate;
- whether tests or narrative artifacts are being substituted for external truth;
- whether negative controls reject missing, stale, mismatched, or tampered evidence;
- whether AI-generated review or approval can silently close the milestone;
- whether future information, hidden state, or unconstrained tools could contaminate results.

Assess every criterion assigned in the review packet. Work read-only, cite exact files or raw evidence, state limitations, and return the supplied JSON template. Use `ABSTAIN` when the available evidence cannot support a responsible verdict.
