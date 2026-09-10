# Wave 1 pre-entry review packet

Prepared 2026-09-10. **Request for a narrow, read-only Astra review.** This is
not an approval, an entry release, or M20 closeout evidence.

## Exact review target

| Item | Bound value |
| --- | --- |
| Application changes | `c192cf9ecbdbc72faf902c923c6cdb98308fe2da`, followed by `dba0a163e393268bb58eb98738bdbe2a0507f3ee` |
| Deployed release | `9f4601f3fd269894` |
| Governed configuration fingerprint | `sha256:a7b8f88a7859ffa00a612b9fa3f76c003a13605a1adf4dfb710dcd78ea3b12ff` |
| Surface | `GOMarketsMU-Demo`, EURUSD, AUD account only |
| Current operating state | listener running in `MAINTENANCE_HOLD`; fresh 2026-09-10 observation shows zero available open positions |
| Policy | Option B; unlimited development trade count, one open position, AUD 100 maximum planned loss, USD 10,000 notional per trade and USD 100,000 cumulative notional |

Review the exact source delta:

```bash
git diff c192cf9^..dba0a16 -- \
  config/runtime.yaml config/schemas/runtime.schema.json \
  src/forex/config/__init__.py scripts/t480_adapter.py \
  t480/command-catalog.json t480/m20_demo_listener_service.py \
  t480/m20_demo_trading_session.py t480/m20_postgres_audit_bridge.py \
  tests/test_m20_financing.py tests/test_t480_adapter.py
```

The later documentation commit `12fe127` records planning and evidence only;
it was not deployed and must not be treated as the reviewed application revision.

## Implemented behaviour to assess

1. New actionable proposals require a qualified financing projection. Unknown,
   stale, unsupported or incomplete fee/calendar inputs make the assessment
   `NO_TRADE`.
2. The calculator supports observed EURUSD points-mode terms and converts USD
   debit using AUDUSD bid, and credit using ask. It includes adverse swap and
   commission allowance in planned loss. A projected credit never enlarges
   Option B risk capacity.
3. Cost coverage reuses this financing result and no longer assumes zero
   commission or swap.
4. Migration 022 and the risk bridge persist each Option B pause reason
   independently. Manual-review reasons survive recovery and reset boundaries;
   an allowed resume removes one qualifying manual reason and requires a fresh
   account check.
5. The deployed policy deliberately has `null` calendar and fee fields. It is
   therefore expected to block normal entries until account-specific broker
   facts are qualified.

## Evidence supplied to review

Raw broker/T480 captures remain ignored and must be read as evidence, not
rewritten:

- `runs/evidence/M20/w1-continuation-20260910/raw/20260910T0324_financing_preview.json`
- `runs/evidence/M20/w1-continuation-20260910/raw/20260910T0324_swap_terms.json`
- `runs/evidence/M20/w1-continuation-20260910/raw/20260910T0325_listener_status.json`
- `runs/evidence/M20/w1-continuation-20260910/raw/20260910T0325_account_liquidity.json`
- `runs/evidence/M20/w1-refusal-final-20260910/raw/`
- `runs/evidence/M20/w1-postgres-refresh-20260910/raw/risk-persistence-tests-rerun.txt`

Separate offline verifiers:

- `runs/verification/M20/w1-continuation-20260910/0325-result.json`
- `runs/verification/M20/w1-refusal-final-20260910/result.json`

Focused engineering evidence: `pytest -q tests/test_m20_financing.py
tests/test_t480_adapter.py` passed 81 tests; the isolated PostgreSQL suite
passed 25 tests. Neither is broker proof.

## Questions for the reviewer

1. Does the signed financing calculation, conversion direction, fee treatment
   and planned-loss integration fail closed under the stated observed mode and
   unknown inputs? Identify any executable path that can bypass it.
2. Do the independent risk latches, resume semantics and reservation checks
   preserve Option B under overlapping drawdown, cash-flow and unknown-account
   states? Identify a state transition that could release an unsafe entry.
3. Does the deployment/rollback posture preserve ledger, lease and risk anchors
   while maintenance hold is active? Identify a material release identity or
   evidence-provenance defect.
4. Are the outstanding facts correctly treated as entry blockers: actual Demo
   account commission arrangement, broker-qualified rollover/DST/holiday
   calendar, exact M20.13 cutoff amendment, genuine protected restart and
   current-release broker lifecycle?

Record findings as `BLOCK_ENTRY`, `REMEDIATION_REQUIRED`, or `NO_CRITICAL_FINDING`,
bound to the values above. A `NO_CRITICAL_FINDING` result does not grant human
authority, remove maintenance hold, substitute for a Triad-plus-domain result,
or complete Wave 1/M20.
