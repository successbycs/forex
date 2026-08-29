# Development platform

The intended platform is the SuccessByCS AI Lab T480: Windows hosts MetaTrader 5; WSL Ubuntu hosts development and future application workloads; shared Docker services provide PostgreSQL, n8n, and optional model runtime capabilities.

M0 inspection confirms a shared T480 transport core exists in `cs-ai-lab-infra` and the Forex adapter imports it through a fixed read-only catalog. The dependency is content-locked by owner repository, full revision and file SHA-256, with tracked-file and clean-worktree requirements. The original untracked-file condition has been resolved: the currently configured shared-core revision and files are tracked and match the lock. This attests only to the dependency boundary while its owner worktree remains clean; it does not prove MT5 API access, Windows/WSL loopback forwarding, a Forex database, or a Forex container deployment. Those require separate real-machine proofs in M1–M5.

PostgreSQL and MT5 must not be publicly or LAN exposed. The actual integration interface and bind address will be selected only after observed connectivity and exposure checks.
