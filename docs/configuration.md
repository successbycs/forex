# Configuration

Human-editable non-secret settings are in `config/*.yaml`. Each document has a schema in `config/schemas` and is loaded into frozen typed models by `forex.config`.

Precedence for M0 is deliberately narrow:

1. Version-controlled YAML provides canonical defaults.
2. `FOREX_LOG_LEVEL` may override logging verbosity.
3. Secrets and machine-local values remain separate environment variables or ignored local files and are never merged into the non-secret snapshot.

No environment variable may override runtime mode, agent authority, live-trading state, server policy, or order availability. Unknown YAML fields and invalid safe overrides fail validation.

Bootstrap T480 transport settings remain in `config/t480.json` because they must work before application dependencies are installed. This governed file also locks the external shared-core owner repository, exact Git revision and safety-relevant file hashes. Environment redirection is prohibited. The fixed operation list remains in `t480/command-catalog.json`. Do not duplicate these values in YAML.

The M1 Windows executable paths are deliberately machine-local. Copy
`t480/mt5.local.example.json` to the T480 as
`%USERPROFILE%\\Documents\\Code\\forex-m1-probe\\mt5.local.json`, then replace
the placeholder Windows user path. The file is ignored by Git and contains
only the local Python and MT5 executable paths; it must not contain account
credentials. The fixed M1 operation accepts no path or command arguments.

`config/triad.yaml` governs the four Review Board roles and fail-closed
recommendation policy at M16, M27, and M32. A policy change invalidates a
recorded Review Board recommendation, not unrelated routine milestone proof.

Validate configuration with:

```bash
python3 -m forex.config --root . --json
```

Evidence records a SHA-256 fingerprint of the effective non-secret configuration. Material configuration changes require fresh verification and proof. Planning-only `target_date` values are not part of that configuration fingerprint.
