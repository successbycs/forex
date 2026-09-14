# Demo autonomy readiness scorecard

## Purpose

This is the standard capability-based progress report for the Forex Waves.
It answers one question only: **how ready is each capability to support
autonomous EUR/USD Demo trading?** It is not a profitability forecast, code
coverage percentage, Live-trading assessment, or substitute for a formal
milestone proof.

## Scoring method

Each percentage is an Astra architecture assessment using the following
evidence ladder:

| Score range | Meaning |
| --- | --- |
| 0–24% | Not designed or no usable implementation. |
| 25–49% | Contract/design exists, or isolated implementation is incomplete. |
| 50–74% | Implemented and tested; an external deployment, input or operational proof remains. |
| 75–89% | Reviewed and deployable/partly deployed; only bounded real-Demo operation or a small critical integration remains. |
| 90–100% | Operating on the required Demo surface with retained, reconciled evidence. |

The combined score is a weighted readiness index, not an average of code
files. Capabilities that can block a new trade carry more weight. A material
schema, policy, execution, account or source-contract change requires the
affected score to be reassessed.

## Baseline — 13 September 2026

| Capability | Wave | Weight | Target readiness | M1 readiness | H_SLOW readiness | Combined readiness | Evidence and remaining critical gap |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Current market analysis | W1/W3 | 10% | **90%** | 75% | 40% | 60% | M1 listener has a fixed Demo EUR/USD quote/closed-bar path; its next natural assessment is market-dependent. H_SLOW has a reviewed read-only preflight but its dedicated terminal binding is not installed/observed. |
| Economic information | W2 | 15% | — | 45% | 45% | 45% | Primary-source capture, provenance and point-in-time context components exist, but current unified primary coverage is unavailable/ambiguous and the entry gate remains disabled. |
| Strategy engine | W2/W3 | 15% | — | 75% | 65% | 70% | M1 has versioned regime/strategy selection and technical trade plans. H_SLOW has defined inactive entry/holding/exit semantics. Neither has yet been evaluated through a complete qualified event-aware Demo loop. |
| Decision engine | W2/W3 | 10% | — | 70% | 55% | 63% | M1 binds final risk/position/calendar vetoes into the proposal. H_SLOW's final decision assembly remains submission-disabled and awaits dedicated-terminal inputs. |
| Risk and sizing | W1/W3 | 15% | — | 85% | 70% | 78% | M1 persistent risk/position controls are in the protected path. H_SLOW fixed AUD 1,000 loss, USD 10,000 notional and one-position rules are reviewed but not broker-observed on its dedicated terminal. |
| Execution engine | W1/W3 | 20% | — | 70% | 30% | 50% | M1 has a fixed Demo-only persisted/reserved/submitted path, pending fresh operating proof/recovery observation. H_SLOW intentionally has no submission adapter or deployed terminal binding. |
| Data and schema | W1/W2/W3 | 10% | — | 75% | 50% | 63% | M1 decisions, attempts and outcomes have PostgreSQL lifecycle records. Calendar fact projection and H_SLOW lifecycle/query deployment are prepared but not deployed. |
| Post-trade analysis | W1/W3 | 10% | — | 70% | 30% | 50% | M1 reconciliation/history reporting exists; fresh operating outcomes remain required. H_SLOW has a read-only reconciliation snapshot design but no dedicated-terminal observation. |
| Operator operations | W1/W3 | 5% | — | 70% | 40% | 55% | M1 listener, schedule/register and retained assessment operations exist. H_SLOW has no installed service, fixed terminal binding or health surface. |
| Research and backtesting *(not an initial Demo-entry gate)* | W2/W3 | — | — | 35% | 35% | 35% | Replay/research components are partial. They are advisory and deliberately do not delay the first bounded Demo decision-and-outcome loop. |

### Readiness totals

| Target | Weighted readiness | What prevents it being operationally complete |
| --- | ---: | --- |
| M1 autonomous EUR/USD Demo stream | **70%** | Fresh natural operation/recovery evidence; qualified current economic context and an explicitly approved enabled gate policy if calendar vetoes are to affect entries. |
| H_SLOW autonomous EUR/USD Demo stream | **47%** | Dedicated H1 terminal binding and read-only broker preflight; fixed execution adapter; deployed isolated lifecycle/reconciliation; qualified event context. |
| Both isolated Demo streams | **59%** | Shared economic-context availability plus the H_SLOW execution and dedicated-terminal path. |

## How this is reported after every package

Every Wave update uses this format:

1. **Capability:** one of the rows above.
2. **Delivered:** the concrete change, not a plan.
3. **Evidence:** tests, review, deployment, broker observation or reconciliation, labelled by strength.
4. **Readiness movement:** prior percentage → new percentage, with reason.
5. **Next critical package:** one bounded package only.
6. **External blocker:** only a precise human-owned decision or external observation, if one exists.

No package is called complete merely because its tests pass. Conversely, a
market closure or an unavailable external observation parks only that
operation; other capability rows continue.

## Immediate priority order

1. Obtain the next natural M1 Demo assessment/recovery observation when the
   broker market is available; do not force a trade.
2. Turn verified primary calendar captures into complete, non-ambiguous
   decision-time context. Keep the event gate disabled unless and until its
   exact activation policy is explicitly approved.
3. Install and verify the isolated H_SLOW Demo terminal binding, then run its
   fixed read-only preflight, financing and reconciliation snapshots.
4. Implement the smallest fixed H_SLOW Demo execution adapter only after the
   preflight proves the intended dedicated account/terminal scope.
