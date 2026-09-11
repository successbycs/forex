# M21 — economic-event context quality

M21 qualifies historical event context before it can be supplied to a decision
or replay. It is not a forecast, signal, trade, scraper, or order surface.

The pipeline accepts only records with an HTTPS source URL, an explicit licence
label, a known availability time at or before the decision cutoff, an exact
local schedule, a valid IANA timezone conversion, and a known scheduled state.
It selects only the latest available revision of an event. Older revisions,
future revisions, cancellations, date-only schedules, malformed provenance, and
DST gaps or unresolved folds are quarantined with machine-readable reasons.

The fixed drill retains source-labelled records from the FRED release-date API
and ECB statistical calendar. FRED's official API warns that its release dates
do not necessarily represent site availability, so its date-only records are
explicitly rejected for intraday use. The ECB calendar publishes forthcoming
statistical releases with CET schedule times; the pipeline converts only an
explicit local timestamp and fails closed at DST boundaries.

M21 proof is a deterministic operational drill. It proves the quality-control
path and retained provenance contract, not a commercial forecast calendar,
complete historical coverage, or any trading authority.
