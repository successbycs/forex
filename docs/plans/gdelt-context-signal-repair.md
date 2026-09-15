# GDELT V3 — retain deduplicated EUR/USD article context and prove the live PostgreSQL result

This ExecPlan is a living document. Maintain it under `PLANS.md` and the
repository governance in `AGENTS.md`, `project_state.json`,
`milestone_registry.json`, and `docs/evidence_and_milestones.md`. The
governance files take precedence. Its machine-readable work record is
`docs/plans/gdelt-context-signal-repair-work.json`; its projection block below
must match that record exactly.

## Purpose / Big Picture

After this work, the running T480 n8n workflow will turn each completed hour's
four GDELT news archives into a real, human-readable EUR/USD *context* record
and retain the fetched publisher title and readable article body for each
eligible document. PostgreSQL will deduplicate the normalized title/body by
content hash, preserve links to the GDELT archive records, and retain the
hourly derived context. It remains research context only: it cannot select,
recommend, submit, modify, or close a trade.

This corrects the deployed placeholder implementation. On 2026-09-15, the
workflow downloaded and staged real archives but its aggregation Code node set
`article_count: 0` and `mean_tone: 0` literally. PostgreSQL therefore has 234
final aggregate rows and 1,170 related provenance rows, but their current
values do not express news content. A successful workflow status is not
acceptance; the end result must include a newly collected, non-placeholder
PostgreSQL row and an operator-readable explanation of it.

This is a bounded M11 research-data repair, not formal M29 work. It does not
advance or close M29, change the current milestone, interact with MT5, grant
broker authority, or change the Demo-only / Live prohibition. It may invalidate
old GDELT research observations because it changes their source-query contract;
it must not be represented as formal milestone proof.

## Progress

<!-- forex-work-projection:start task=GDELT-V2 schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=baseline state=DONE -->
- [x] baseline — Record the deployed placeholder behavior and scope the repair (DONE)
<!-- forex-work-item id=execution-authorisation state=DONE -->
- [x] execution-authorisation — Confirm Chris explicitly instructed execution of this ExecPlan (DONE)
<!-- forex-work-item id=parser-contract state=DONE -->
- [x] parser-contract — Define and test the fixed in-memory GKG relevance and tone contract (DONE)
<!-- forex-work-item id=article-retention-design state=DONE -->
- [x] article-retention-design — Define and test publisher retrieval, extraction, retention, and content deduplication (DONE)
<!-- forex-work-item id=workflow-and-schema state=DONE -->
- [x] workflow-and-schema — Implement the versioned workflow, metrics migration, and bounded installer update (DONE)
<!-- forex-work-item id=tests state=IN_PROGRESS -->
- [ ] tests — Run focused unit, workflow, and PostgreSQL integration checks (IN_PROGRESS)
<!-- forex-work-item id=review state=PENDING -->
- [ ] review — Obtain independent read-only review and repair findings (PENDING)
<!-- forex-work-item id=deploy state=PENDING -->
- [ ] deploy — Deploy the reviewed fixed workflows to the existing private T480 n8n service (PENDING)
<!-- forex-work-item id=live-observation state=PENDING -->
- [ ] live-observation — Verify one newly collected live PostgreSQL aggregate and render the operator result (PENDING)
<!-- forex-work-projection:end -->

- [x] (2026-09-15) Observed the defect through the actual T480 n8n execution
  `614` and PostgreSQL, then authored this repair plan. The plan is not yet
  authorised for implementation or deployment.
- [x] (2026-09-15) Chris explicitly instructed execution. Parser-contract work
  began; no T480 mutation has occurred.
- [x] (2026-09-15) Chris explicitly authorised controlled retrieval from the
  publisher URLs present in eligible GDELT records and retention of the
  retrieved title and body. This supersedes the earlier derived-metrics-only
  decision below.
- [x] (2026-09-15) Terra completed the literal-Code-node parser fixture,
  original-ZIP hash node, V2 parser, and V2 stage SQL. Its focused parser/M11
  suite passed (11 tests); the coordinator's parser/M11/adapter suite passed
  15 tests. Schema/import/deployment compatibility remains in progress.
- [x] (2026-09-15) Terra repair attempt 1 corrected the V3 batch branch so it
  processes every candidate, refuses redirects and literal IP targets, and
  records every publisher retrieval attempt. Local deployment remains pending.
- [x] (2026-09-15) Astra material repair replaced the direct n8n publisher
  HTTP node with a loopback-only bounded egress service. It validates fixed
  candidate metadata, revalidates every redirect, pins the chosen public IP
  for TLS, and caps the stream at one MiB. The workflow sends candidate data
  only to this service. Local tests and an independent review remain pending.
- [x] (2026-09-15) Astra final local repair separated the private n8n bearer
  from the HMAC candidate-signing key, added the ignored T480-local Compose
  hand-off contract, bound every fetch envelope to its immutable aggregate,
  made same-aggregate stage retries resumable, and returned the exact
  PostgreSQL `attempt_id` to the receipt update. The focused local suite
  (`tests/test_gdelt_publisher_egress.py`,
  `tests/test_gdelt_article_retention.py`,
  `tests/test_gdelt_context_v2.py`,
  `tests/test_n8n_m11_install_v3.py`, and `tests/milestones/test_m11.py`)
  passed 25 tests. No remote component has been changed.
- [x] (2026-09-15) Astra release repair made the n8n Code-node builtin grant
  explicit and minimal (`crypto,net`), moved the egress caller path onto a
  dedicated Docker-internal network, and left publisher HTTPS reachable only
  from the egress container's separate outbound network. The installer now
  verifies matching owner-only n8n and Docker-secret files, builds from the
  fixed Forex repository root, and Docker-inspects the exact build-input
  digest label. Its n8n-namespace preflight posts a valid signed localhost
  candidate (which must be refused before DNS) and a bad signature (which
  must be refused), so it proves matching authentication and signing values
  without contacting a publisher. A rollback-only PostgreSQL integration
  runner was added for the deployed schema. Local validation passed 35 tests;
  no remote component has been changed and the rollback runner has not been
  executed against T480.
- [x] (2026-09-15) Astra repaired the final pre-deploy review findings locally:
  n8n now has no outbound Docker network, while PostgreSQL bridges its new
  private network and only `gdelt-egress` has a distinct outbound network. The
  four fixed GDELT archive pulls cross that same bounded service. Docker COPY
  exactly matches the digest manifest; the rollback integration mirrors the
  workflow's returned-attempt receipt update; and the installer applies,
  inspects, health-checks, and rolls back its Compose fragment as one bounded
  operation. A 33-test focused suite passed. No T480 change occurred.

## Surprises & Discoveries

- Observation: the n8n HTTP Request node can limit timeout and disable
  redirects, but this installed workflow surface has no trustworthy option to
  stop receiving a response at one MiB or to pin a validated DNS address.
  Evidence: the V3 workflow limits retained bytes only after the response is
  already available to the Code node. V3 deployment is therefore held at local
  implementation until a bounded egress fetcher is supplied or this residual
  risk is explicitly accepted.

- Observation: Compose build paths are resolved relative to the Compose file
  that imports a fragment, not necessarily this repository. A relative
  `../../` build context could therefore package the shared-infrastructure
  repository rather than the reviewed Forex source. Evidence: the release
  repair uses a fixed-root Docker build in the installer and changes the
  Compose fragment to consume its verified image tag.

- Observation: the present aggregation node hashes the extracted CSV and then
  labels it as an archive source hash. It also uses the first source hash as
  the aggregate hash.
  Evidence: `n8n/forex-gdelt-daily.json`, node `Aggregate one closed hour of
  context`, calls `getBinaryDataBuffer(i,'file_0')`, assigns its digest to
  `payload_sha256`, and assigns `r[0].payload_sha256` to `aggregate_sha256`.

- Observation: the deployment does write both provenance and final aggregate
  records to PostgreSQL.
  Evidence: the read-only T480 verification returned 1,170 GDELT-linked
  `raw_observation` rows and 234 `gdelt_h1_aggregate` rows on 2026-09-15.
  The defect is semantic extraction, not the PostgreSQL hand-off.

- Observation: a bearer check alone authenticates n8n but does not prove that
  the URL came from the fixed GDELT aggregation node. The old receipt update
  also selected the most recent URL attempt, which could associate concurrent
  attempts incorrectly.
  Evidence: the previous workflow body contained only `canonical_url` and
  `sources`, and its receipt query used `max(attempt_id)`. Both are replaced
  by a canonical HMAC envelope and `RETURNING attempt_id` hand-off.

## Decision Log

- Decision: retain n8n as scheduler and PostgreSQL hand-off, but move
  publisher network retrieval into `src/forex/gdelt_publisher_egress.py`. It
  listens only on `127.0.0.1:8092` and exposes exactly one POST route that
  accepts fixed GDELT candidate metadata. It accepts no commands, headers,
  credentials, or caller-selected network options. The installer verifies its
  loopback health endpoint before activating the workflow.
  Rationale: this minimal service can resolve every hop, reject non-global
  destinations, pin the selected public address, and enforce byte limits that
  n8n's HTTP node cannot reliably provide.
  Date/Author: 2026-09-15 / Astra after two Terra repair attempts.

- Decision: V3 disables saved n8n success, error, manual, and progress
  execution data. Publisher bytes can exist in n8n memory while a run is
  active, but must not be retained in its execution-history database. The
  PostgreSQL article and attempt tables are the durable retention surface.
  Rationale: a private-volume handoff would need a second privileged service
  to persist content and is not justified for this MVP. This setting is a
  deployment contract and must be observed on T480 before activation.

- Decision: use two different ignored T480-local values: an n8n-to-egress
  bearer and an HMAC candidate-signing key. Egress verifies a canonical,
  signed `{aggregate_sha256,bucket_time_utc,candidate}` envelope before it
  resolves any hostname. The deployment package injects the values only into
  n8n and Docker secrets; tracked configuration contains paths and names, not
  values.
  Rationale: possession of the bearer on its own must not be enough to turn
  the egress service into a generic public URL fetcher.
  Date/Author: 2026-09-15 / Astra.

- Decision: an existing `gdelt_hourly_stage.stage_id` may be resumed only if
  its saved aggregate digest and hour exactly match the newly computed values.
  A mismatch raises a database error. Article attempts remain append-only and
  the receipt update uses the `attempt_id` returned by its own insert.
  Rationale: a transient failure after staging can be retried without hiding
  a changed source result or attaching egress facts to a different attempt.
  Date/Author: 2026-09-15 / Astra.

- Decision: preserve the existing two-workflow PostgreSQL hand-off rather
  than create another scheduler or service.
  Rationale: the download/stage workflow and independent import workflow are
  already live, isolated, and restartable. Replacing them would expand scope
  without improving the extraction defect.
  Date/Author: 2026-09-15 / Codex.

- Decision: retain a fetched publisher title and readable body for eligible
  GDELT documents, plus their canonical URL and source links. Deduplicate by
  the SHA-256 of a deterministic normalized title/body representation; retain
  many GDELT source links to one content record rather than duplicating
  syndicated copies. Do not retain account data, trade direction, score, or
  order data.
  Rationale: Chris explicitly requires readable source content. GKG itself
  supplies metadata and publisher URLs, not a title or article body, so the
  workflow must retrieve only the eligible publisher pages.
  Date/Author: 2026-09-15 / Chris and Codex.

- Decision: deduplicate publisher content only by the normalized title/body
  hash, with URLs in a separate mapping history and one no-body retrieval
  ledger row per attempted candidate.
  Rationale: URL uniqueness loses changed pages; URL-only identity also fails
  to join syndicated copies. Attempt records make rejected redirects and bad
  responses observable without retaining their bodies.
  Date/Author: 2026-09-15 / Terra repair attempt 1.

- Decision: add nullable source-row and tone-sample metrics for new V2 rows
  instead of rewriting old V1 placeholder rows.
  Rationale: a zero count is otherwise indistinguishable from a missing
  parser. Null metrics identify historical V1 placeholders without changing
  retained observations; non-null V2 metrics make the live result explainable.
  Date/Author: 2026-09-15 / Codex.

## Outcomes & Retrospective

No implementation outcome exists yet. The expected outcome is a new V2 row
whose source-row count, matching-document count, tone-sample count and mean
tone were computed from the four downloaded archives, plus an independently
verified PostgreSQL read-back. If a natural hour genuinely has no matching
documents, the result may correctly be zero, but it must still prove parsing by
showing a positive source-row count and V2 query version.

## Context and Orientation

`n8n/forex-gdelt-daily.json` is the active hourly workflow. It runs at five
minutes after the hour, constructs the four 15-minute GDELT GKG archive URLs
for the previous closed UTC hour, downloads and unzips them, then writes one
row to `forex.gdelt_hourly_stage`. `n8n/forex-gdelt-hourly-import.json` runs at
twelve minutes after the hour and moves one complete staged row into
`forex.gdelt_h1_aggregate`.

GKG is GDELT's tab-separated Global Knowledge Graph file. It contains one
record per source document and a `V2Tone` field whose first comma-separated
number is GDELT's document tone, plus a publisher document URL. It is an
external descriptive measurement, not a prediction of EUR/USD price. It does
not contain an article title or body. The parser must emit only eligible,
deduplicated publisher URLs to the bounded retrieval branch; non-eligible GKG
text remains in memory only and is discarded.

### V3 publisher-content contract

The aggregation node emits at most five unique eligible HTTPS URLs per closed
hour, in deterministic URL order. The candidate list is transient pipeline
data: it is never put into the stage or hourly-aggregate PostgreSQL rows. It
rejects non-HTTPS URLs, every literal IPv4/IPv6 address, localhost names,
credentials in URLs, and URLs longer than 2,048 characters. This is syntax
validation only. The standard n8n HTTP node neither pins DNS resolution nor
enforces a network response-size ceiling; it cannot claim protection against
DNS rebinding or a 1 MiB download. That residual deployment blocker must be
accepted or replaced by a bounded egress fetcher before live V3 deployment.

The retrieval branch makes one GET request per candidate with a fixed user
agent, 10-second timeout, no redirects, and no credentials. It explicitly
rejects every 3xx response. The extractor retains at most 1 MiB of received
publisher bytes and caps stored title/body; it does not claim n8n avoided
receiving a larger response. Failed, oversized, non-HTML, redirected, or
inaccessible pages each become a recorded retrieval attempt and never block
the hourly context aggregate.

An extraction Code node removes scripts, styles, navigation markup, and HTML
tags; decodes basic entities; collapses whitespace; obtains the first nonempty
`<title>` and readable text. It rejects an empty title/body and caps retained
title at 500 characters and body at 100,000 characters. The extracted body is
stored as retrieved text, not represented as a publisher-authoritative source
or trading signal. `content_sha256` is the SHA-256 of canonical normalized
`title + "\\n" + body`; it is the sole content-deduplication key. A separate
URL-mapping table is deliberately nonunique by URL: a changed body at the same
URL creates a new content record and mapping history, while identical content
from different URLs maps to one article. A retrieval-attempt table records one
result per candidate without title/body fields on failures. A many-to-many
source-link table preserves every GDELT document and hour that observed the
retained article. No prior data is deleted or rewritten.

`forex.raw_observation` retains source metadata and hashes. The stage table is
the durable hand-off between n8n workflows. The final aggregate table is the
only research-facing hourly context record. The existing
`scripts/postgres_pgvector_adapter.py` contains fixed read-only M11 checks;
`scripts/postgres_admin_adapter.py export-html` produces a credential-free
operator report. `scripts/n8n_m11_install.py` is the T480-local installer that
updates only the named Forex GDELT workflows using the T480-local n8n API key.

## Design and Plan of Work

First create an executable parser contract rather than adding an opaque block
of JavaScript. Add `tests/fixtures/gdelt_v2_context_rows.tsv` containing
synthetic, small, tab-separated GKG V2 rows: one EUR/USD-relevant positive
tone, one relevant negative tone, one duplicate document identifier, one row
with blank tone, and irrelevant rows. The fixture must contain no real article
URL, headline, or body. Add a small test runner that evaluates the exact Code
node source with n8n-shaped fake binary buffers; it must not reproduce parsing
logic in Python. This ensures the code tested is the code n8n deploys.

The fixed V2 relevance rule is deliberately simple and versioned as
`eurusd-context-terms.v2`. For each decoded TSV row, form a temporary uppercase
search string from the GKG theme, location, person, and organisation fields.
It is relevant only when it contains an EUR anchor (`EUR`, `EURO`, `EUROZONE`,
`ECB`, or `EUROPEAN_CENTRAL_BANK`) and a USD/macro anchor (`USD`, `DOLLAR`,
`FED`, `FEDERAL_RESERVE`, `FOMC`, `US_INFLATION`, `CPI`, `EMPLOYMENT`, or
`NONFARM`). A direct `EURUSD` token is also relevant. The implementation must
use exact token-boundary matching, not substring matching, so `EURO` does not
match an unrelated longer word. Count a matching document once per unique GKG
document identifier within the hour. Parse only finite first values of
`V2Tone`; `article_count` includes all matched documents and `tone_sample_count`
counts the subset with a numeric tone. `mean_tone` is zero only when the tone
sample count is zero; otherwise it is the arithmetic mean rounded to six
decimal places.

Amend `n8n/forex-gdelt-daily.json` as follows. Insert a `Hash downloaded GKG
ZIP` Code node between `Download GKG ZIP` and `Extract GKG ZIP`. It hashes the
original `data` ZIP bytes with SHA-256, records only the digest on the item's
JSON metadata, and leaves the binary for decompression. This corrects the
meaning of `raw_observation.payload_sha256`: it will refer to the downloaded
archive rather than the decompressed CSV. Replace `Aggregate one closed hour
of context` with bounded in-memory TSV parsing. It must reject an input count
other than four, missing archive digest, a GKG file over 32 MiB after
decompression, non-UTF-8 replacement characters, malformed required columns,
or a generated result inconsistent with its input hour. It emits the following
durable aggregate fields plus a transient `article_candidates` list used only
by the publisher branch:

    stage_id, bucket_time_utc, source_records, aggregate_sha256,
    article_count, source_row_count, tone_sample_count, mean_tone,
    query_definition_version, uncertainty_label, retrieved_at_utc,
    article_candidates

`source_records` contains only the four deterministic IDs, revisions, UTC
observed/available times, archive SHA-256 values, and redacted `n8n://` paths.
`aggregate_sha256` is the SHA-256 of canonical JSON containing the ordered four
source records, V2 query version, source-row count, article count,
tone-sample count, and mean tone. The workflow must never put an article
title/body, document identifier, URL, theme string, account field,
recommendation, or order field into stage or aggregate persistence SQL.
Candidate URLs and GDELT links are transient inputs only to the publisher
retrieval branch.

Add `sql/migrations/024_m11_gdelt_derived_metrics.sql`. It must add nullable
`source_row_count INTEGER CHECK (source_row_count >= 0)` and
`tone_sample_count INTEGER CHECK (tone_sample_count >= 0 AND tone_sample_count
<= article_count)` to both the stage and final aggregate tables. Null means a
legacy V1 row; V2 writes both values. Do not update or delete existing rows.
Update the stage and import SQL in the two workflow files to insert and carry
the two V2 fields atomically. Update the fixed M11 verifier to report the
latest V2 bucket, its V2 query version, the four archive hashes, positive
source-row count, matching count, tone-sample count, and final lineage. Keep
the existing no-article-columns and context-only checks.

Add `sql/migrations/025_m11_gdelt_article_retention.sql`. It creates
`forex.gdelt_article` with the normalized content hash, title, body, and
retrieval facts; `forex.gdelt_article_url` for URL mapping history;
`forex.gdelt_article_retrieval_attempt` for each attempted candidate; and
`forex.gdelt_article_source` with a unique article/source-document/hour link.
It enforces content-hash uniqueness, text limits, mapping history, failure
records without bodies, and provenance links. Its upserts never replace a
previously retained title/body; historical aggregates and stages remain
untouched.

Update `scripts/n8n_m11_install.py` to load and apply migrations 024 and 025 before it
upserts the two fixed workflows. Its only external effects remain the existing
private n8n/PostgreSQL operations; it must not add generic commands, URLs,
credentials, public listeners, retries, broker access, or a new container.
The deploy is an idempotent update: it deactivates the named workflows during
replacement, imports their V2 definitions, then reactivates only those named
workflows. It must preserve the unrelated A1 workflow and all other n8n work.

Do not overwrite historical V1 zero rows. After deployment, wait for the next
natural completed UTC hour. The V2 row has a different query version and
non-null parser metrics. A natural zero matching count is valid only when
`source_row_count > 0` and `tone_sample_count = 0`; it is evidence of no match,
not a parser failure. A non-zero fixture test is required even if the live hour
has no match.

## Concrete Steps

All local commands run from `/home/chris/projects/forex`.

1. Capture the pre-change read-only baseline and record it in this plan.

       python3 scripts/postgres_pgvector_adapter.py forex-m11-verify-data
       python3 -m pytest -q tests/milestones/test_m11.py

   The observed baseline currently reports 234 aggregates whose newest rows
   have `article_count=0`, `mean_tone=0`, and V1 query version.

2. Implement the exact-node fixture runner and tests before changing the
   workflow. The synthetic fixture must assert a deterministic result of two
   unique matching documents, one numeric tone sample, and the expected mean
   tone; duplicate and irrelevant rows must not change that result. Add
   negative tests for more/fewer than four files, oversize binary input,
   missing archive hash, malformed tone, and a prohibited output field.

3. Implement the ZIP hash node, V2 aggregation source, migration 024, stage
   SQL, import SQL, installer migration application, and fixed verifier. Run:

       python3 -m pytest -q tests/milestones/test_m11.py tests/test_gdelt_context_v2.py
       python3 scripts/postgres_pgvector_adapter.py forex-m11-verify-schema

4. Run a local, transaction-rolled-back PostgreSQL integration test that stages
   a V2 fixture result, invokes the exact import SQL, reads the final row, and
   confirms all four hashes plus `source_row_count`, `article_count`,
   `tone_sample_count`, and `mean_tone`. The test must leave no database row.
   Then run the focused suite and the applicable governance validation:

       python3 -m pytest -q tests/milestones/test_m11.py tests/test_gdelt_context_v2.py tests/test_n8n_forex_adapter.py
       python3 scripts/forex_milestones.py validate

5. Obtain an independent read-only Astra review after the implementer has
   recorded test output. If a material defect is found, record each Terra
   repair attempt here; after two failed Terra repairs, Astra owns the repair
   and another independent read-only reviewer inspects it. Tests and review do
   not close M29 or any registry milestone.

6. Deploy only after the review accepts the exact source revision. From the
   existing T480 route, use the fixed installer; do not use a general n8n API
   client, Docker shell, or pasted credential.

       python3 scripts/n8n_forex_adapter.py preflight
       python3 scripts/n8n_forex_adapter.py upsert --approve

   Verify both fixed workflow IDs are active and that no unrelated workflow was
   changed. Observe the next 05-minute collection and 12-minute import runs;
   do not manufacture a row or alter a V1 row to make the outcome look good.

7. Read the actual result from PostgreSQL and render the read-only report.

       python3 scripts/postgres_pgvector_adapter.py forex-m11-r1-verify-hour
       python3 scripts/postgres_pgvector_adapter.py forex-m11-verify-data
       python3 scripts/postgres_admin_adapter.py export-html --output reports/gdelt-context-v2.html

   If local PostgreSQL desktop settings are intentionally unavailable, use the
   fixed T480 verification commands for the acceptance result and do not copy
   the shared `.env` to make the HTML export work. The browser report can be
   generated later from an operator-configured local connection.

## Validation and Acceptance

Implementation acceptance requires the fixture runner to execute the exact
n8n Code-node source and demonstrate a non-zero derived result. It must show
that duplicates are counted once, irrelevant rows are excluded, invalid tones
do not poison the mean, no content fields are emitted, and all error cases
fail closed.

Deployment acceptance requires a T480 transcript with both named GDELT
workflows active, an inspected topology where n8n has no outbound network and
only the bounded egress service has publisher egress, a new successful
collection execution, a subsequent import, and a fixed verifier result for a
V2 aggregate. The verifier must report four
source hashes, `source_row_count > 0`, V2 query version,
`tone_sample_count <= article_count`, one final aggregate linked to its hourly
provenance row, no content columns, and `EXPERIMENTAL_CONTEXT_ONLY`.

The human-readable operator outcome must state the UTC hour, number of GKG
rows scanned, unique relevant-document count, tone sample count, mean tone,
and the meaning: negative is more negative GDELT language, positive is more
positive language, and zero samples means no eligible tone—not neutral market
direction. It must explicitly say this is context only and does not create a
trade instruction.

## Idempotence and Recovery

The migration is additive and repeatable. The installer can be re-run: it
updates only the two fixed workflow names, reuses the named PostgreSQL
credential, and leaves other workflows untouched. If deployment fails after
deactivation, rerun the same installer after correcting the recorded defect;
it restores the same named workflows from the reviewed files. If the parser
rejects a live archive, keep the failed n8n execution and its source metadata,
do not stage a partial aggregate, and investigate from a fixture before retry.

Rollback means upserting the previously recorded workflow JSON revision and
reactivating only the two named workflows. Do not delete source hashes, stage
rows, aggregate rows, n8n execution history, or database provenance. Do not
roll back by changing historical V1 values.

## Artifacts and Notes

The live defect observed before this plan was:

    execution 614
    stage_id: gdelt-h1-2026091421
    article_count: 0
    mean_tone: 0
    query_definition_version: eurusd-context-terms.v1

The new acceptance output will resemble this shape, with real values rather
than invented example numbers:

    bucket_utc=2026-..-..T..:00:00Z
    source_rows=<positive integer>
    relevant_documents=<integer>
    tone_samples=<integer no greater than relevant_documents>
    mean_tone=<derived decimal or 0 when tone_samples is 0>
    query=eurusd-context-terms.v2
    context_only=true

## Interfaces and Dependencies

The n8n Code node must expose one result item with the exact JSON fields named
in the plan; the PostgreSQL nodes accept no caller-selected SQL or connection.
The test helper must provide the n8n-compatible `this.helpers.getBinaryDataBuffer`
surface and `$input.all()` items, allowing the literal workflow JavaScript to
run unchanged under test. The only added network surface is the bounded egress
service: it permits the four fixed GDELT archive URL form and GDELT-selected,
HMAC-bound publisher URLs. No credential, public listener, broker endpoint, or
generic URL input is added.

## Plan revision note

Created 2026-09-15 after live inspection established that the current GDELT
workflow persists provenance but hard-codes zero content metrics. The revision
defines the smallest useful correction: parse in-memory, retain only derived
metrics, preserve the existing n8n-to-PostgreSQL hand-off, and prove a new V2
row on T480.
