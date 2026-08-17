# Development platform

The intended platform is the SuccessByCS AI Lab T480: Windows hosts MetaTrader 5; WSL Ubuntu hosts development and future application workloads; shared Docker services provide PostgreSQL, n8n, and optional model runtime capabilities.

M0 inspection confirms a shared T480 transport core exists in `cs-ai-lab-infra` and the Forex adapter imports it through a fixed read-only catalog. Current M0 does not claim that MT5 API access, Windows/WSL loopback forwarding, a Forex database, or a Forex container deployment exists. Those require separate real-machine proofs in M1–M5.

PostgreSQL and MT5 must not be publicly or LAN exposed. The actual integration interface and bind address will be selected only after observed connectivity and exposure checks.
