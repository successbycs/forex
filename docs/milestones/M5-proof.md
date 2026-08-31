# M5 — idempotent PostgreSQL persistence

The Forex application uses the fixed T480 PostgreSQL adapter to retain the
Demo-only historical snapshot. Reimport checks the canonical snapshot hash and
reports already-present data instead of duplicating or replacing it.
