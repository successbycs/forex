# M11 — n8n-native experimental GDELT aggregate sentiment

M11 uses a T480 n8n workflow, not a Python scheduler, to retain a fixed
EUR/USD-relevant aggregate-tone query, source-file retrieval time, hash and
uncertainty label. It retains no article text and is context only—not a
signal, recommendation or order input. The daily workflow fetches the prior
closed UTC day's GDELT intervals, normalizes H1 aggregates, and persists them
through the n8n PostgreSQL credential. A single latest GDELT interval cannot
be described as a daily dataset.

The Forex-owned `scripts/n8n_forex_adapter.py` imports only this fixed
workflow through the shared T480 transport. Its T480-local installer creates
or reuses the n8n PostgreSQL credential from the lab's existing `.env`; it
does not copy the n8n API key or database password into this repository or
accept a generic workflow, shell, SQL, MT5, or order argument. The first
real execution must be inspected in n8n execution history and verified against
the normalised PostgreSQL rows before M11 evidence can be captured.

For one-shot proof runs, the installer also maintains a fixed inactive n8n
wrapper named `Forex M11 fixed evidence runner`. Its Manual Trigger calls the
M11 workflow through M11's Execute Workflow Trigger. This avoids treating the
daily Schedule Trigger as a command-line job, while keeping retrieval, ZIP
extraction, aggregation and persistence entirely inside n8n. The wrapper has
no scheduler, host command, credential, SQL or order surface.

`capture_m11_evidence.sh` records only the latest bounded n8n execution
summary and fixed PostgreSQL schema/data verification. Its paired verifier
checks revision, artifact hashes, 168-hour freshness, successful n8n
execution, provenance linkage, and absence of article-text fields.
