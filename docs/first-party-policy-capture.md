# First-party FOMC / ECB retained-input and timing-bundle retention

This local command stores bytes you have already retained. It does not fetch a
publisher page, schedule work, deploy anything, access MT5, or change a trade.

Calendar pages establish the meeting date only. Exact event time requires a
second, already-retained official timing declaration. Supply both local files
and their separately declared capture-completion times to the immutable local
timing-bundle command:

```bash
python3 scripts/retain_first_party_policy_timing_bundle.py \
  /local/fomc-calendar.html /local/fomc-timing-declaration.html \
  --store /local/forex-policy-timing --family FOMC_POLICY_DECISION \
  --target-date 2026-01-28 \
  --calendar-capture-completed-at 2026-09-13T00:00:00Z \
  --timing-capture-completed-at 2026-09-13T00:01:00Z
```

Use `ECB_POLICY_DECISION` for ECB input. The root is machine-local and must be
explicit. The store publishes calendar/timing bytes, their closed receipts,
the hash-bound timing bundle, projected event record, and a manifest once per
family/target date. An exact retry returns `EXISTING`; conflicting, partial,
symlinked, or tampered state is refused.

The FOMC calendar must contain the target meeting range in its declared year
section, and its separate declaration must state a policy statement at exactly
2 p.m. or 2:00 p.m. Eastern. The ECB calendar must contain one target
monetary-policy Day 2 entry; its separate declaration must state publication
at exactly 14:15 CET. Missing/ambiguous date, time, source URL, or DST data is
refused rather than inferred.

This is still a local retention and projection operation: it never fetches,
schedules, deploys, accesses MT5, changes a gate, or changes a trade. A
successful local retention reports `coverage_status: UNKNOWN` and
`qualification_state: PENDING_RETAINED_CAPTURE`. It does not qualify FOMC or
ECB for primary event context until a separate real source-qualification
amendment is reviewed and made deliberately active.

To inspect a completed local timing store without changing it:

```bash
python3 scripts/verify_first_party_policy_timing_store.py \
  --store /local/forex-policy-timing
```

The report emits individually verified, provenance-bound observations in the
primary-context input shape. It deliberately leaves coverage `UNKNOWN`; more
retained dates do not silently become complete source coverage.

To render those verified observations through the current primary-event
context contract (still read-only and still subject to its PENDING source
state):

```bash
python3 scripts/report_primary_event_policy_timing_context.py \
  --store /local/forex-policy-timing \
  --contract config/primary_event_context.json
```

Multiple retained dates for the same publisher source are intentionally passed
through as multiple observations. The context report marks that source
`AMBIGUOUS`; it never silently selects one schedule.

## BLS monthly retained-source verification

The corresponding read-only BLS verifier validates the retained HTTP receipt,
raw HTML, immutable capture metadata, parser projection, and journal before
reporting CPI/Employment candidate context observations:

```bash
python3 scripts/verify_bls_primary_source.py --store /local/forex-bls-captures
```

Chris approved the exact BLS monthly URL-template amendment. The active
contract matches only official concrete `YYYY/MM_sched_list.htm` URLs under
the bounded template; it leaves retained BLS coverage `UNKNOWN`/`PARTIAL`, not
complete, and keeps duplicates fail-closed. The original draft remains retained
as approval provenance.

The proposed bounded template interpretation is deliberately non-active in
`docs/milestones/W2-bls-monthly-url-template-amendment-draft.json`. Inspect its
machine-validated delta without changing the current contract:

```bash
python3 scripts/report_bls_url_template_amendment.py \
  --baseline config/primary_event_context.json \
  --draft docs/milestones/W2-bls-monthly-url-template-amendment-draft.json
```

It matches only official BLS `YYYY/MM_sched_list.htm` URLs and requires a
separate human-approved amendment before any active contract can change. That
approval has now been supplied and the draft's exact bounded result is active.

Render verified BLS evidence through the active primary context, read-only:

```bash
python3 scripts/report_bls_primary_context.py \
  --store /local/forex-bls-captures \
  --contract config/primary_event_context.json
```

Chris approved the FOMC/ECB timing-source amendment on 2026-09-13. The active
contract now matches only exact retained timing-manifest observations for the
specified FOMC 2026-09-16 and ECB 2026-10-29 evidence. Coverage remains
`UNKNOWN`/`PARTIAL` and context-only; this does not enable an event gate,
select direction, change sizing, or create order authority. The original draft
is retained as approval provenance and may still be inspected read-only:

```bash
python3 scripts/report_policy_timing_amendment.py \
  --baseline config/primary_event_context.json \
  --draft docs/milestones/W2-policy-timing-source-qualification-amendment-draft.json \
  --store runs/local/first-party-policy-timing
```
