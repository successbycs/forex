# Loss-accounted M20 assessment exporter

These are templates for the authorised orchestrator's user manager. Render
absolute local paths and validate the result with `systemd-analyze --user
verify` before linking the units. Rendered files and retained responses stay
under ignored `runs/local/` paths.

The service runs the fixed paged `m20_listener_spool_page` adapter operation.
It supplies only its locally retained numeric cursor and has no broker,
listener-control, order or configuration surface. A page is accepted only when
every source byte hash, sequence and active release binding matches. It mirrors
immutable source records and retains full local captures before moving its
local cursor. It never deletes or acknowledges a Windows source record.

The two-minute timer drains up to eight source records per pass. A source page
is bounded; it is not proof of unbroken listener availability or M20/M29.
Do not interpret timer activation, absence, or a successful local capture as
broker proof. The listener release which creates the source remains a separate
controlled deployment and revalidation action.
