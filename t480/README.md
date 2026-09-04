# Forex T480 adapter

The Forex repository owns a fixed catalog of T480 operations. Reusable
PowerShell, Windows OpenSSH, WSL, timeout, validation, and audit behavior is
supplied by `cs-ai-lab-infra/t480_core`.

The shared core is an external safety dependency, so Forex will use it only
when its owner repository is clean, its files are tracked, its full Git
revision matches, and every locked file SHA-256 matches `config/t480.json`.
`CS_AI_LAB_INFRA_ROOT` cannot redirect the import. To inspect the binding:

```bash
python3 scripts/t480_adapter.py dependency-status
```

`preflight`, `execute`, `verify`, M0 evidence capture, independent evidence
verification, Triad review, and closeout all fail closed when this identity is
not exact. After an authorised shared-core change, commit the owner repository,
update the revision and hashes in the governed Forex configuration, and capture
fresh proof.

Configure the private SSH target outside Git:

```bash
cp .env.example .env.t480.local
# Set T480_SSH_TARGET to the existing private SSH alias.
chmod 600 .env.t480.local
python3 scripts/t480_adapter.py preflight
python3 scripts/t480_adapter.py execute --operation forex_preflight
python3 scripts/t480_adapter.py execute --operation mt5_process_status
```

Operator-editable non-secret paths, the dependency lock, Docker names, and MT5 process names are in
[`config/t480.json`](../config/t480.json). Shared transport security and
timeouts are controlled by `cs-ai-lab-infra/t480/transport-config.json`.
Strict host-key checking and SSH batch mode cannot be disabled.

The adapter cannot deploy or alter the T480. Most operations are inspection
only. M20 has one exception: `m20_demo_trading_session` is a no-argument,
hash-bound `GOMarketsMU-Demo`/`EURUSD` session path. Before it contacts MT5 it
requires an ignored machine-local lease with fixed Demo-only exposure limits,
one-position, USD 100-per-trade and USD 1,000 cumulative limits, plus audit
prerequisites. It must fail closed on any mismatch. It is not a generic MT5,
symbol, account, shell, or broker-control interface, and it is not proven or
deployed simply because the local code exists.

Execution output is returned to the invoking operator, but the ignored local
audit log retains only timestamps, exit status, byte counts, and SHA-256
hashes. Credentials and raw remote output are not persisted by the adapter.
