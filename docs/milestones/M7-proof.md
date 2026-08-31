# M7 — external source qualification

M7 is a source-selection gate, not a downloader or a trading feature. It
retains a small, reviewable registry of macro, calendar and sentiment candidates
with a decision, licence constraint, retention rule and later adoption gate.

Current decisions are deliberately conservative:

| Candidate | Decision | Why |
| --- | --- | --- |
| FRED/ALFRED | Conditionally qualified | It has vintage-aware facilities, but an API key and series-owner copyright check are required before M8. |
| ECB Data Portal | Qualified | Official statistics, SDMX revision facilities and a documented reuse policy support M9, subject to attribution and third-party-data exclusions. |
| Trading Economics calendar | Deferred | A paid/licensing and historical forecast/revision decision is required before M10. |
| GDELT | Experimental aggregates only | It may support an M11 prototype; no article text is retained and it is not a signal or execution input. |

The fixed M7 capture samples only publicly accessible documentation/endpoints.
It does not use credentials, scrape a calendar, ingest data into PostgreSQL, or
adopt a source that the registry has deferred. The verifier checks that the
observed endpoints are the same ones named in the registry and that every
candidate has an explicit decision and adoption gate.

Official sources consulted at capture time are retained as bounded, hash-checked
samples: FRED API documentation and terms, ECB SDMX dataflow metadata, Trading
Economics documentation availability, and GDELT data access documentation.
