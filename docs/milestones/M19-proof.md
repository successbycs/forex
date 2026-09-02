# M19 — decision and model lineage persistence

## Purpose

M19 stores one validated M18 local-model research observation in the Forex
PostgreSQL schema so it can be reproduced and inspected later. It persists the
bounded input payload, output payload, hypothesis, model definition, prompt,
input/output hashes, source, application revision, configuration fingerprint
and validation result.

## Fixed T480 path

```text
M2 retained Demo-only EUR/USD H1 snapshot
  -> M17 bounded historical context
  -> fixed local qwen2.5:3b request and strict validation
  -> model_inference_lineage + research_decision_lineage
  -> fixed read-only lineage verification
```

The fixed operations are `forex-m19-apply-schema`,
`forex-m19-lineage-probe`, and `forex-m19-lineage-verify`. They do not accept
SQL, host, database, model, prompt, MT5, account, order or shell arguments.

## Boundary

Only retained `DEMO_ONLY_HISTORICAL` input is persisted. The decision state is
always `RESEARCH_ONLY`; no order, broker server, account, credential or
execution column is created. Lineage rows are immutable once written. M19
does not evaluate trading quality or authorise an action.
