# A1 local implementation review — 2026-09-14

This is implementation evidence, not raw publisher evidence, deployment
approval, Triad recommendation or formal milestone closeout.

Terra (`/root/a1_implementation`) implemented the envelope, retention, service
and verified projector. The primary agent implemented the workflow/deployment
package and reviewed Terra's result. Independent read-only reviewer
`/root/review_loop` accepted both packages after the timestamp repair below.

Findings resolved: deterministic receipts replace retry-time receipt drift;
inputs validate before publication; projection verifies the n8n-specific receipt
instead of assuming shared-transport equivalence; a real `.123Z`/`.123000Z`
timestamp spelling mismatch was reproduced and repaired by Terra on the first
review repair attempt. The reviewer reran the regression and accepted it.
The workflow test now proves exact non-UTF8 byte preservation. Independent
review ran 33 passing checks. No deployment or database write was performed.

Final independently reviewed SHA-256 file digests:

```text
5bd8987c00831dfd4b8a4bcad02d9518ce259aff63c132e28bc6c07c45db879f  src/forex/bls_n8n_envelope.py
27a5363ea0b503ab9a479fdc7049b6ddaf537a3516de9d9e211b18d055563bf3  src/forex/bls_n8n_projection.py
02c4425e0855b2148425a939ddc9bb1bbe2f11268cef17f2727116378b825c62  src/forex/bls_n8n_retention.py
a74f2ec23e1f795d3b8cb6ea2ff7db39010b181a9711f110f33514b34a54b477  src/forex/bls_n8n_service.py
4af78e01de943bbd63a115de4f430dde8a5a4921be25e8cef3e30eaf624c5a74  scripts/run_bls_n8n_service.py
7eb767030c4038ea3b19b4adf7d66f184c9f8f6822350f75e791ff2f04ca0226  scripts/validate_bls_n8n_handoff.py
7703b50b1adde4a271718edd1dfcecd019938afa85f5a633914faa1d4cc5d8ab  scripts/project_n8n_bls_retained_calendar_facts.py
7fca26feddf5d07262ac6850b562006b69f12ea77678d5c5b83df0044ccaeb10  scripts/persist_bls_retained_calendar_facts.py
1074d87b7f4bdcebe6e5e6fc91afe24b13033bb0c00990e841d4c50690e59264  scripts/build_bls_n8n_workflow.py
08b997b6eb837cd44af0ee3a843fda2ccb4d95a86f158de7ceb5624a2a02a990  n8n/forex-bls-calendar-retention.json
821b0d447a8d8dfea6d5a97a4bd65a0f70897cbb0d1ba1bbc5ef97919a04603f  tests/test_bls_n8n_workflow.py
d653d190dce0903bab7bf515c54df95d53342a212695a4592afff365f6694608  deploy/bls-n8n/Dockerfile
dad0c5c542c7a2683e93ba7e2a0ca3f42a9c52622eed9821c53a7d3c922da0dc  deploy/bls-n8n/README.md
```

Repository regression found one remaining failure outside this package:
`tests/test_report_policy_timing_amendment_cli.py::test_cli_reports_nonactive_timing_draft`
rejects the W2 draft because its pending source family no longer matches the
canonical baseline. The test, draft, baseline, CLI and implementation files are
unchanged from HEAD. No source qualification policy was relaxed to pass it.
The whole suite is therefore not reported green. Database-dependent tests skip
when their isolated DSNs are absent; those skips are not database observations.
