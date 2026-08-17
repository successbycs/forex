# Forex T480 adapter

The Forex repository owns a fixed, read-only catalog of T480 inspection
operations. Reusable PowerShell, Windows OpenSSH, WSL, timeout, validation, and
audit behavior is supplied by `cs-ai-lab-infra/t480_core`.

Configure the private SSH target outside Git:

```bash
cp .env.example .env.t480.local
# Set T480_SSH_TARGET to the existing private SSH alias.
chmod 600 .env.t480.local
python3 scripts/t480_adapter.py preflight
python3 scripts/t480_adapter.py execute --operation forex_preflight
python3 scripts/t480_adapter.py execute --operation mt5_process_status
```

Operator-editable non-secret paths, Docker names, and MT5 process names are in
[`config/t480.json`](../config/t480.json). Shared transport security and
timeouts are controlled by `cs-ai-lab-infra/t480/transport-config.json`.
Strict host-key checking and SSH batch mode cannot be disabled.

The initial adapter cannot deploy or alter the T480. `mt5_process_status` uses
Windows process inspection only. It does not import MetaTrader, connect to an
account, inspect the configured broker server, retrieve prices, or expose any
order operation. Those capabilities require their own later milestones and
real-world proof.

Execution output is returned to the invoking operator, but the ignored local
audit log retains only timestamps, exit status, byte counts, and SHA-256
hashes. Credentials and raw remote output are not persisted by the adapter.
