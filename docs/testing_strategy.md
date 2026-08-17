# Testing strategy

M0 tests cover typed configuration, schema rejection, safety invariants, catalog locking, dependency gates, worktree-independent negative controls, evidence hashes, sign-off requirements, and closeout refusal.

Verification has three layers:

1. Unit and contract tests run quickly in the development checkout.
2. `scripts/verify_project.sh` validates configuration, governance, compilation, adapter requirements, and the non-empty test suite.
3. `scripts/capture_m0_evidence.sh` creates a new virtual environment without system packages, installs the declared project and test dependencies, runs verification, and retains raw output. `scripts/verify_m0_evidence.sh` independently checks the bundle.

Later milestones must add milestone-specific tests and real-surface proof. Mocks may test failure handling but cannot prove external capability.
