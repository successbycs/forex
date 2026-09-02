# System design: EUR/USD price and GDELT context data

## Purpose and current boundary

This design supports inspectable EUR/USD historical research with attributable
GDELT-derived context. It has no live-account access, order command,
autonomous execution, or profitability claim.

| Component | Current status |
| --- | --- |
| T480 PostgreSQL and Forex schema | Implemented; price data present |
| EUR/USD H1 data | One `DEMO_ONLY` 720-bar snapshot present |
| Raw GDELT retrieval and H1 aggregate | T480 n8n workflows stage and finalise bounded H1 aggregates |
| GDELT PostgreSQL persistence and backfill | Proven for retained hourly aggregate/provenance rows; scheduled operation remains bounded and Demo-only |
| Price/GDELT join and replay | M13 fixed read-only T480 replay probe deployed; it applies a UTC availability and event-time cutoff |
| T480 n8n adapter | Fixed Forex M11 adapter is deployed to the T480 |
| Daily Forex n8n schedule | n8n-native design; not deployed or activated |

## System topology and ownership

```text
T16 operator laptop
  ├─ pgAdmin/DBeaver (administrator access only)
  └─ Forex repository tools
          │ existing shared transport
          ▼
T480 Windows + WSL
  ├─ MetaTrader 5 (Demo-only historical source)
  ├─ Forex checkout: adapters, collectors, research code
  └─ cs-ai-lab-infra Docker services
      ├─ PostgreSQL + pgvector
      └─ n8n (private loopback API)
```

`cs-ai-lab-infra` owns transport, Docker, PostgreSQL, n8n, credentials and
backups. Forex owns the `forex` schema, source contracts, collectors, workflow
definitions, research logic and evidence. Shared infrastructure does not own
Forex trading or research logic.

## Existing PostgreSQL design

| Table | Purpose | Important fields |
| --- | --- | --- |
| `source_registry` | Source catalogue | source ID, owner, licence, endpoint allowlist, approval status |
| `raw_observation` | Retrieved artifact metadata | source/revision, observed/available time, SHA-256, retained path |
| `dataset_snapshot` | Bounded research dataset | EUR/USD instrument, timeframe, decision cutoff, artifact hash |
| `dataset_snapshot_observation` | Snapshot/input lineage | snapshot ID, observation ID |
| `price_bar` | Normalised OHLCV | snapshot ID, UTC time, OHLC, volume, availability time |

`price_bar` is the existing price fact table. Its primary key is
`(snapshot_id, time_utc)`. The current data is one `DEMO_ONLY` EUR/USD H1
snapshot with 720 bars. This database is research persistence, not a generic
MT5, shell or order interface.

## Proposed GDELT extension

M11-R1 separates n8n responsibilities without nesting workflows: the hourly
download-and-stage workflow stores a bounded four-file hand-off in
`forex.gdelt_hourly_stage`; the independently scheduled import workflow
finalises only complete stage records into `forex.gdelt_h1_aggregate`. The
handoff is PostgreSQL, never an n8n subworkflow call.

GDELT source-file lineage uses the existing `source_registry` and
`raw_observation` tables. M11 then adds one lean derived table:

```text
forex.gdelt_h1_aggregate
  aggregate_id             text primary key
  observation_id           text → forex.raw_observation(observation_id)
  bucket_time_utc          timestamptz
  available_at_utc         timestamptz
  article_count            integer
  mean_tone                numeric
  query_definition_version text
  uncertainty_label        text
  created_at_utc           timestamptz

  unique (observation_id, bucket_time_utc)
```

This holds aggregate measures only—no headline, article URL, article text,
account data, trading decision or order. The raw ZIP remains under the
operator retention policy; its path and SHA-256 are held in `raw_observation`.

The first research join is a view or named read operation, not a duplicate
price table:

```text
price_bar.time_utc = gdelt_h1_aggregate.bucket_time_utc
AND gdelt_h1_aggregate.available_at_utc <= decision_cutoff_utc
```

The target is a later outcome, for example next-H1 return. The current bar
close must never be used to decide that same bar.

## GDELT collector contract

The collector takes a public GDELT 2.0 raw GKG ZIP and:

1. Uses a fixed, versioned EUR/USD-context relevance-term set.
2. Records source URL and SHA-256.
3. Parses in memory and does not retain article text.
4. Groups matching records into UTC H1 buckets.
5. Emits `article_count`, `mean_tone`, source lineage, query version and an
   `EXPERIMENTAL_CONTEXT_ONLY` uncertainty label.
6. Preserves `available_at_utc` separately from the event/bucket time.

The first successful sample, `20260831071500.gkg.csv.zip`, produced one H1
aggregate of 96 matching records with mean tone `-2.5102`. It is an integration
observation, not a market conclusion.

## n8n and adapter design

The fixed Forex M11 adapter calls the shared T480 n8n transport and the
n8n-loopback REST API. The n8n API key lives only on T480; it is neither read
nor copied into the Forex repository. The adapter has no caller-selected host,
credential, workflow, command, SQL, MT5, or order parameter. Supported
operations are:

| Operation | Purpose | Mutates state |
| --- | --- | --- |
| `preflight` | Check private n8n health and key presence | No |
| `list-workflows` | Inspect workflows | No |
| `get-execution` | Inspect one execution | No |
| `upsert` | Import/update the one fixed M11 workflow | Yes, explicit approval |
| `activate` | Import/update and activate that fixed daily schedule | Yes, explicit approval |

The deployable daily workflow is not an n8n command node pointing to the host
worktree. That worktree is not mounted in the n8n container. It is n8n-native:
Schedule Trigger, HTTP Request, Compression, Code, Aggregate and PostgreSQL
nodes run the entire daily flow. There is no Python scheduled job. The required
shape is:

```text
n8n Schedule Trigger, after UTC day closes
  → build every prior-day GKG interval URL
  → HTTP download + ZIP extraction + bounded JavaScript aggregation
  → PostgreSQL insert/upsert of raw-observation + H1 aggregate rows
  → one hourly worker downloads four 15-minute archives and derives one H1 aggregate
  → one import worker persists that bounded aggregate and four source records
  → return counts, source hashes, time range and failures to n8n
  → n8n retains execution history for the operator
```

One read of GDELT `lastupdate.txt` is one 15-minute interval, not a daily
aggregate. Historical backfill uses the same collector contract, with an
explicit bounded date range and volume budget.

## Operator inspection and delivery sequence

### Read-only operator research view

The MVP operator view should be a generated, read-only HTML report produced
from fixed adapter reads. It is a data-inspection surface, not a trading
terminal, database console, or dashboard with write controls. Its first screen
should show:

| Section | Operator question answered |
| --- | --- |
| Dataset health | Which source and snapshot are present; how many bars/features; what is the UTC coverage? |
| Freshness | What is the most recent closed EUR/USD bar and GDELT aggregate; when were they available? |
| Price context | Recent H1 OHLCV rows and a simple price chart once chart rendering is added |
| GDELT context | H1 article count, mean tone, uncertainty label and source-file lineage |
| Alignment | How many price/GDELT H1 rows overlap and which rows were excluded for late availability? |
| Research boundary | `DEMO_ONLY`, historical/context-only, no order controls, and no demonstrated edge |

The existing `postgres_admin_adapter.py export-html` command is the first
version of this surface. It exports only the allowlisted Forex tables, including
the GDELT aggregate table. M13 also has a fixed read-only alignment report on
the T480. A browser report has no database credentials and no write operation.

### ML: what we will train and when

ML is valuable only after the data is clean and time-aligned. We will not train
directly on raw article material or give a model execution authority. The M15
baseline will use a versioned row set such as:

```text
decision_time_utc
price-only features: lagged returns, realised range/volatility, session
macro/calendar features: approved, available-at-cutoff values only
GDELT features: article count, mean tone and changes, available-at-cutoff only
target: next-H1 direction or pre-declared intraday-session result
```

M12 first quarantines malformed, duplicate, late and unverifiable records.
M13 then proves the time-aligned replay dataset. M14 adds deterministic regime
and event-window features. Only then does M15 train one small explainable
offline classifier, producing a research-only 0–100 advisory score and
`BUY`/`SELL`/`NO_TRADE` hypothesis for human inspection. M16 compares it with
price-only and no-change baselines in chronological walk-forward windows.

M20 separately evaluates six strict, local-Ollama historical sentiment
observations against the same simple price-only direction and `NO_TRADE`
comparators. It retains bounded result hashes and descriptive metrics only;
the local model cannot issue an order or reach a broker.

Success is not a high in-sample score. The model must improve a pre-declared
out-of-sample comparison after costs and retain an abstaining `NO_TRADE`
outcome. Until then, the operator view reports research observations, not a
recommendation to trade.

The current database can be inspected with:

```bash
python3 scripts/postgres_admin_adapter.py tables
python3 scripts/postgres_admin_adapter.py schema --table price_bar
python3 scripts/postgres_admin_adapter.py read --table price_bar --limit 20
python3 scripts/postgres_admin_adapter.py export-html
```

After its migration, `gdelt_h1_aggregate` will be explicitly added to the
adapter catalogue; the adapter will not gain generic SQL or shell access.

Delivery order:

1. Test and finalise M11 source contract and aggregate collector.
2. Add the lean GDELT migration and named adapter operation.
3. Backfill a bounded window overlapping EUR/USD history and inspect counts.
4. Add the point-in-time join/replay contract in M13.
5. Configure the T480-local PostgreSQL credential in n8n and then
   import/activate its workflow after one observed successful manual run.

None of these steps permits live trading or order placement.
