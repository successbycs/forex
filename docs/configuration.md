# Configuration

Human-editable non-secret settings are in `config/*.yaml`. Each document has a schema in `config/schemas` and is loaded into frozen typed models by `forex.config`.

Precedence for M0 is deliberately narrow:

1. Version-controlled YAML provides canonical defaults.
2. `FOREX_LOG_LEVEL` may override logging verbosity.
3. Secrets and machine-local values remain separate environment variables or ignored local files and are never merged into the non-secret snapshot.

No environment variable may override runtime mode, agent authority, live-trading state, server policy, or order availability. Unknown YAML fields and invalid safe overrides fail validation.

Bootstrap T480 transport settings remain in `config/t480.json` because they must work before application dependencies are installed. The fixed operation list remains in `t480/command-catalog.json`. Do not duplicate these values in YAML.

`config/triad.yaml` governs required review roles, assigned M0 criteria and fail-closed recommendation policy. Review-policy changes alter the governed configuration fingerprint and invalidate existing review recommendations and proof.

Validate configuration with:

```bash
python3 -m forex.config --root . --json
```

Evidence records a SHA-256 fingerprint of the effective non-secret configuration. Material configuration changes require fresh verification and proof. Planning-only `target_date` values are not part of that configuration fingerprint.
