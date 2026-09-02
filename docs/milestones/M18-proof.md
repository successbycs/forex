# M18 — controlled Ollama sentiment assistance

## Purpose

M18 proves one fixed local Ollama request on the T480 using only the bounded
historical context defined by M17. It produces a small schema-constrained
research response or an explicit abstention. It is not a trading signal,
order, execution capability, or performance claim.

## Fixed proof path

```text
Retained Demo-only EUR/USD H1 bars
  -> M17 point-in-time bounded context
  -> fixed M18 prompt + JSON schema
  -> local T480 Ollama qwen2.5:3b
  -> strict response validation or failure
  -> retained proof result with model, prompt, input and output hashes
```

The fixed T480 adapter operation `forex-m18-ollama-probe` has no caller-supplied
model, prompt, database, host, shell, MT5 or order arguments. The result must
identify `FOREX_M18_OLLAMA_PROBE_OK` and retain the exact model-definition,
input-context and output hashes in the evidence bundle.

## Safety boundary

- Only `GOMarketsMU-Demo` retained historical data is used.
- `GOMarketsMU-Live`, live trading, account data, credentials and MT5 controls
  are not inputs.
- The only valid results are `POSITIVE`, `NEGATIVE`, `NEUTRAL` and `ABSTAIN`.
  `ABSTAIN` always has zero confidence.
- A model result remains research-only. It has no order capability and cannot
  create or transmit a trade instruction.

## Completion evidence

`scripts/capture_m18_evidence.sh` will capture the fixed probe, local M18
tests, governance validation, the clean revision and hashes. The independent
verifier checks all artifacts and current model/prompt/context bindings before
M18 may be signed off and proved.
