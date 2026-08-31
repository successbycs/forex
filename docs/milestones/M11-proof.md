# M11 — n8n-native experimental GDELT aggregate sentiment

M11 uses a T480 n8n workflow, not a Python scheduler, to retain a fixed
EUR/USD-relevant aggregate-tone query, source-file retrieval time, hash and
uncertainty label. It retains no article text and is context only—not a
signal, recommendation or order input. The daily workflow fetches the prior
closed UTC day's GDELT intervals, normalizes H1 aggregates, and persists them
through the n8n PostgreSQL credential. A single latest GDELT interval cannot
be described as a daily dataset.
