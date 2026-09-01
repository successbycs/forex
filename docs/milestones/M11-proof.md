# M11 — n8n-native experimental GDELT aggregate sentiment

Current recovery work is sequenced in [M11-R1 — bounded n8n recovery and
real-world check](M11-recovery-plan.md). It is a work package, not a second
milestone state machine.

The required supporting implementation and deployment guide is
[M11 system design](M11-system-design.md). It defines the decoupled T480 n8n
workflows, PostgreSQL staging hand-off, verification checks and recovery cap.

M11 uses a T480 n8n workflow, not a Python scheduler, to retain a fixed
EUR/USD-relevant aggregate-tone query, source-file retrieval time, hash and
uncertainty label. It retains no article text and is context only—not a
signal, recommendation or order input. The daily coordinator creates 24
closed UTC hour jobs. Each hourly worker fetches exactly four 15-minute GKG
archives, derives one H1 aggregate, and hands one bounded redacted record to
the import workflow. This makes every hour independently observable and
retryable: one failed archive cannot remain hidden inside a 96-file run. A
single latest GDELT interval cannot be described as a daily dataset.

The Forex-owned `scripts/n8n_forex_adapter.py` imports only these three fixed
workflows through the shared T480 transport. Its T480-local installer creates
or reuses the n8n PostgreSQL credential from the lab's existing `.env`; it
does not copy the n8n API key or database password into this repository or
accept a generic workflow, shell, SQL, MT5, or order argument. The first
real execution must be inspected in n8n execution history and verified against
the normalised PostgreSQL rows before M11 evidence can be captured.

The fixed `trigger-now` adapter command may start the same workflow immediately
through a T480-local n8n webhook and waits for its normal n8n result. It is for
an operator-run recovery or initial capture only; the normal production
collection remains the UTC schedule. The webhook is not internet-exposed and
accepts no caller-selected workflow, URL, SQL, or data payload.

`capture_m11_evidence.sh` records the latest successful daily coordinator
execution and fixed PostgreSQL schema/data verification. Its paired verifier
checks revision, artifact hashes, 168-hour freshness, successful n8n
execution, provenance linkage, and absence of article-text fields.
