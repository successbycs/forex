# Event publisher integration

Implementation mapping inspected on 2026-09-12. Preserve the existing M10
FRED/ECB statistical-calendar adapter; the policy-event sources below are
additional W2 ingestion work under the cross-wave goal.

| Event family | Official surface | Remaining implementation |
| --- | --- | --- |
| US CPI and Employment Situation | [BLS CPI](https://www.bls.gov/schedule/news_release/cpi.htm), [Employment Situation](https://www.bls.gov/schedule/news_release/empsit.htm), [calendar feed documentation](https://www.bls.gov/help/hlpiCAL.htm) | Parse release reference month, date and time. The ICS endpoint returned 403 during inspection; do not invent its field format. |
| FOMC | [Annual dates](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm), linked monthly news calendars | Parse meeting dates separately from statement/press-conference timestamps; do not apply today's normal release time to historical events. |
| ECB monetary policy | [Governing Council calendar](https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html), [policy timing](https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html) | Select monetary-policy Day 2, excluding Day 1/non-monetary meetings. Qualify the CET wording and seasonal timezone interpretation before labelling exact UTC timing. |

Retain the downloaded bytes, source URL, capture completion timestamp, payload
hash and parser version. First capture supplies conservative availability;
these public calendars do not establish historical first-publication time.
Keep first-observed timestamps when unchanged data is fetched again. Assign
explicitly local revisions when normalized content changes and preserve the
prior versions. A missing event in a later page is not proof of cancellation.

Source qualification needs explicit BLS, Federal Reserve Board and ECB
policy-calendar entries; existing FRED/statistical entries do not cover them.
Review the source-specific terms when implementing collection:
[BLS](https://www.bls.gov/opub/copyright-information.htm),
[Federal Reserve](https://www.federalreserve.gov/disclaimer.htm),
[ECB](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html).

Feed normalized records through the existing qualification and annotation
modules. Keep coverage unknown until the publisher set, retrieval health and
date range are qualified. Date-only metadata remains date-only. No event
direction, calendar veto or new order rule is introduced by this ingestion.

Implementation checkpoint: `bls_events.py` parses the retained BLS family
schedule shape; `scripts/bls_event_context.py` connects raw-file hashing,
parsing, qualification and annotation. Capture time remains caller-supplied,
not authenticated. `event_revisions.py` retains normalized capture content and
parser quarantines, preserves first availability for unchanged records, and
derives local revisions with originating capture IDs. Journal validation
reconstructs revisions from retained captures; integrity is not publisher
authentication. This is a pure value adapter, not durable storage.

Remaining publisher parsers and operational attachment remain to implement.
Immutable raw capture and scheduled BLS collection are now deployed separately
as described below. These components do not constitute complete source
qualification or a trading-authority grant.

Subsequent integration: local immutable storage/recovery is implemented, and
`bls_monthly_events.py` now feeds the same storage and annotation path through
`bls_capture.py --monthly-url`. The separate W2 `config/event_sources.json`
records the selected BLS public-calendar usage scope; see the
[source assessment](reviews/bls-event-source-scope.md). Scheduled collection,
authentic raw publisher demonstration, other publisher parsers and operational
attachment remain pending. Existing M7 source decisions are preserved.

## Current independent deployment dependencies

The late-capture recovery path now has an explicit immutable isolation marker
and `scripts/bls_isolate_capture.py`; subsequent captures proceed without
rewriting the published journal. The annotation command reports omissions as
current storage health, separate from decision-time event context. This does
not establish publisher authenticity or healthy coverage.

The deployed service uses a fixed BLS acquisition operation through shared
transport, bounded cadence/timeout/retry settings, retained acquisition
failure evidence, a product-owned service definition and health/rollback
checks. The M20 listener remains outside this deployment surface.

A read-only `t480_adapter.py execute --operation storage` observation completed
at 2026-09-12T02:43:58Z: Windows C: had 16.8 GiB free of 235.6 GiB. The shared
infrastructure `docs/project-foundation.md` currently directs no new persistent
service at that headroom, since Docker/WSL growth consumes the physical drive.
The operation response is retained in the ignored adapter execution log; this
paragraph is a summary, not raw proof. Resolve that host-capacity requirement
before persistent deployment. Do not automatically delete host data. This
dependency does not block collector/service implementation or local checks,
and is independent of M29's pending market observation.

## Fixed one-pass collector

`scripts/bls_collect.py --year YYYY --month MM --capture-id ID --store PATH`
now carries the fixed `t480/bls_monthly_probe.py` payload through the existing
shared T480 transport. It requests only the selected BLS monthly calendar,
performs no redirects/retries, bounds the response to 2 MiB, and uses a
20-second socket timeout within the canonical collection policy's 35-second
transport deadline. It does not install files or a service on T480.

The local store retains the actual transport result with probe/source hashes
and the exact returned HTTP-observation JSON in separate content-addressed
files. A complete successful HTML response alone proceeds to the existing
monthly parser. HTTP errors, access denials and oversized responses are retained
as failures and cannot become a healthy empty calendar. `--resume` processes
retained data only, including recovery after transport retention but before
capture publication. Use a new capture ID for a separately authorized new
request; no automatic retry loop is implemented.

Exit 0 means successful response processing, not complete calendar coverage;
exit 3 reports a retained retrieval failure, and exit 2 is an invocation,
transport or integrity refusal. Coverage remains UNKNOWN. This is a one-pass
collector, not yet a scheduled service or an order-context attachment.

Observed one-pass result, 2026-09-12T02:59:44.873Z: the permitted shared-T480
path returned a successful September 2026 BLS HTML response. The raw body is
retained under `runs/evidence/W2/bls-collector-20260912/raw/bls-september-streamed.html`,
SHA-256 `3f9ee4b1f431e0e8cb8d8a2234aa2b149a1be9811ef5b820bbf286722c2e0e72`.
The monthly parser selected CPI and Employment Situation with no parser
quarantine; the read-only annotation path qualified two records. Their local
availability starts at capture completion, not at the earlier release dates.
Two earlier Windows command-length failures are separately retained; they
did not reach the publisher. Compacting and streaming the fixed payload
resolved that transport constraint without installing a remote file/service.

Transport receipts bind the original probe and source declaration; subsequent
receipts also bind the compacted program hash. The first successful receipt
predates that extra field and is intentionally unchanged. Shared transport
strips surrounding stdout whitespace; the retained observation is exactly
the text it returned, while the base64-decoded publisher body is preserved.
Successful `--resume` reproduced the same journal without another request.
This observation establishes one functioning collection/parsing path, not
publisher-authenticated historical availability, complete coverage, scheduled
operation or a formal milestone completion.

## Scheduler integration

`python3 scripts/bls_schedule.py --store <retained-store>` is a one-pass
scheduling entry point. It reads canonical `config/bls_scheduler.json` and
the actual UTC clock; it exposes no historical-clock override or trading
operation. The proposed policy collects the current and following calendar
months on hourly buckets, with a publisher-wide minimum 24-hour backoff for
403/429 responses. Collector summaries now expose retained HTTP status and
capture completion time; raw observations remain unchanged.

The scheduler retains a claim before invoking the fixed collector. An
unresolved claim permits local `--resume` processing only, never a fresh
request under that identity. A timeout or invalid child response requires
inspection/recovery of retained state, not deletion of the claim. The command
uses an argument-list subprocess with a 90-second bound, greater than the
collector's maximum transport deadline, and performs no automatic retry.

The entry point itself does not install or activate a timer. Its reviewed user
units have since been installed under the existing authorised deployment
scope; persistent operation remains subject to the previously recorded
physical-host capacity requirement.
The ledger rejects clock rollback against actual claim times, including
rollback within an hourly bucket. Changing interval policy uses elapsed time
for completed collections under older policies; an unresolved claim still
requires its original policy. Results are validated before immutable
publication. Access-denial backoff applies to any retained 403/429, including
oversized or truncated responses.

The CLI rebuilds the collector summary from retained bytes before accepting
it. A local end-to-end crash/recovery test exercises the actual resume
subprocess and verifies raw capture, metadata, journal and acquisition bytes
remain unchanged. Parser quarantine is a list of reasons, retained as such;
it never grants complete coverage. Prepared user service/timer templates and
activation prerequisites are in [deploy/bls](../deploy/bls/README.md).
The local scheduler was activated as recorded below. This is not a formal
milestone-closeout or complete-calendar-coverage claim.

Release scope reviewed before local activation: W2 scheduler/collector and
annotation-only retained store on the separate Piwakawaka orchestrator. The
T480 receives only its existing fixed read-only public-calendar operation;
no remote service is installed. M1 trading runtime, order schemas, risk caps,
account selection and active M29 real-market recovery surface are unchanged.
This W2 implementation/configuration needs its own operational observation;
it cannot satisfy M29 or restore M27/M28 proof. Renderer, rendered units and
local transport dependencies have independent technical review, not human
impersonated sign-off or formal milestone approval. Activation is scoped by
the owner's existing independent-component deployment instruction.

Local deployment observation, 2026-09-12: reviewed units under ignored
`runs/local/bls-service-render-reviewed-20260912` were linked to Piwakawaka's
systemd user manager. The service completed successfully at 03:19:57 UTC.
September and October requests completed at 03:19:54.635Z and 03:19:56.734Z,
both HTTP 200 with empty parser-quarantine lists. Captures, acquisitions and
scheduler ledger are retained in ignored `runs/local/bls-event-store`.
The resulting journal digest is
`sha256:af336b66555524aa60ec6e0077c0bc2dfc5eea02c3d3df67e8ab7f4f25d0aa4e`.
The timer is enabled and active; its first scheduled trigger was reported as
16:00 NZST (04:00 UTC). It depends on this host and its user manager remaining
available; no missed-run catch-up or guarantee of operation while the machine
is asleep is implied. Service activation does not enable trade vetoes, new
orders or a remote service, and the T480 capacity restriction remains intact.
