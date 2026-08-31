# M11 — n8n-native experimental GDELT aggregate sentiment

M11 uses a T480 n8n workflow, not a Python scheduler, to retain a fixed
EUR/USD-relevant aggregate-tone query, source-file retrieval time, hash and
uncertainty label. It retains no article text and is context only—not a
signal, recommendation or order input. The daily workflow fetches the prior
closed UTC day's GDELT intervals, normalizes H1 aggregates, and persists them
through the n8n PostgreSQL credential. A single latest GDELT interval cannot
be described as a daily dataset.

The Forex-owned `scripts/n8n_forex_adapter.py` imports only this fixed
workflow through the shared T480 transport. It does not copy the n8n API key
or accept a generic workflow, shell, SQL, MT5, or order argument. The first
real execution must be inspected in n8n execution history and verified against
the normalised PostgreSQL rows before M11 evidence can be captured.
