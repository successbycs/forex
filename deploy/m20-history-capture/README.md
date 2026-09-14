# Daily all-Demo-history retention

These templates deploy a **read-only** daily user service. Render absolute
plain local paths, validate the result with `systemd-analyze --user verify`,
then link the reviewed units into the authorised user's manager. Rendered
units and retained captures belong under ignored `runs/local/` paths.

The service invokes only `scripts/m20_all_history_capture.py`, which invokes
the fixed `m20_all_demo_history_export` T480 adapter operation. A response is
published only after strict Demo/EURUSD/M20 report validation, as immutable
raw response, report and receipt bytes. It never submits an order, changes a
listener, changes configuration, acknowledges/deletes source data, or makes a
strategy/risk decision.

The timer runs at 17:05 in the host's local time with `Persistent=false`: a
missed pass is not replayed on boot. It is intentionally daily rather than a
market-polling loop. Retention consumes roughly the current fixed response
size per day; review the ignored capture directory periodically under the
operator's retention policy. A successful capture is retained operational
history only. It does not establish broker continuity, cost completeness,
profitability, M20/M29 proof, or authority to activate H_SLOW.
