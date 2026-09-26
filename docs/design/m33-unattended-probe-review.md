# M33.1 bounded feasibility probe review

Independent read-only reviewer: `/root/m33_probe_review`, 24 September 2026.
Scope: the fixed no-order Session-0 observation, not unattended readiness or
production recovery. The reviewer recommended execution after repairs.

Required repairs addressed: refuse active production listener/trading workers
in addition to requiring Disabled listener task; refuse Queued and Running
probe tasks; retain baseline observation filenames and accept only new receipts
with observation time after dispatch receipt. A very fast child timestamp can
be conservatively rejected by this last rule; do not relax it after seeing data.

Reviewed SHA-256 identities:

| File | SHA-256 |
|---|---|
| scripts/t480_adapter.py | d65722c72a7dbb731a661e4ac532dcb71f2ebca94e2dea5bd0f866fa78db539e |
| t480/command-catalog.json | c97cf8dbdb14f6cd8266b5878ab52ceee0201bded03a681d6528b18ea4a78030 |
| t480/m30_single_client_probe.py | 5b626e77f37c8f6ed143abd2b806a6dfa8ffc3c197b2e97c74aa41303f6a618b |
| tests/test_m33_unattended_probe.py | 92f4d53c295f9acf9041f508a25dbf4e0a77fba8767e5dc1c7f1d75e4df773e8 |

The 168-test adapter/probe regression run passed before the final worker/Queued
repairs; both focused new safety tests passed again after those repairs.
The reviewed encoded launcher is 7,166 characters, below the 7,500 limit.
Raw test output and fixed-operation receipts are retained under
`runs/local/m33-health-wave1/20260924T074012Z`.

The observer hash is checked before dispatch. Same SID, configured executable,
sole visible terminal and Session 0 are checked. Child-process restriction and
its canary precede MT5 import. No order API, terminal restart or production task
mutation is introduced. Probe task is bounded to one minute with IgnoreNew.

Limitations: process observation precedes dispatch, accessible process inventory
is incomplete, and MT5 has no native PID attachment binding here. This evidence
can establish only the actual observed Session-0 account/API behavior.
