# Prepared BLS scheduler user units

These tracked files are **templates only**. Reviewed machine-local renderings
were linked into Piwakawaka's user manager on 2026-09-12. The first service
pass succeeded and the hourly timer is enabled/active. No remote T480 service
was installed. See the publisher integration note for observed results.

The unit is for the current Forex orchestrator host. It starts the local,
one-pass `scripts/bls_schedule.py` entry point, which in turn uses the existing
governed shared T480 transport for its single bounded public BLS request. It
does not install a collector, a service, or any executable on the T480 native
host. It has no broker, order, or calendar-eligibility authority.

## Current hold

Do not install unresolved templates. The shared infrastructure capacity record
for 2026-09-12 holds new services on the remote T480 because of physical C:
headroom. It does not impose a global hold on this separate orchestrator.
Piwakawaka was checked locally: Windows C: had 402,888,261,632 bytes free of
1,021,821,579,264, and its systemd user manager was running. The local scheduler
retains data here and installs no remote T480 service. This is a
host-specific deployment gate, not an M29 market-proof gate. Preparing and
testing these tracked templates does not demonstrate a scheduled service,
healthy publisher coverage, source authenticity, or a milestone completion.

## Values that an operator must supply later

Copy rendered units to a user-owned systemd unit directory only after the
actual destination host's requirements have been verified. Replace
these literal placeholders with absolute local paths:

- `{{FOREX_REPOSITORY_ABSOLUTE_PATH}}`: the reviewed Forex checkout containing
  `scripts/bls_schedule.py`.
- `{{PYTHON_EXECUTABLE_ABSOLUTE_PATH}}`: the reviewed Python interpreter for
  that checkout.
- `{{BLS_RETAINED_STORE_ABSOLUTE_PATH}}`: a dedicated, trusted local capture
  store. It must not be tracked or shared as a mutable cross-product volume.
- `{{OPTIONAL_T480_ENVIRONMENT_FILE_ABSOLUTE_PATH}}`: an optional ignored,
  mode-0600 operator environment file if the host needs one for the existing
  shared T480 transport. Do not put its path, aliases, credentials, or values
  in these tracked templates. The current adapter also resolves its established
  local transport configuration independently; this unit does not replace or
  redirect that mechanism.

The service uses an argument-vector `ExecStart`, not a shell. It has no retry
or restart loop. `TimeoutStartSec=210s` is derived from the scheduler's maximum
two collector subprocesses at 90 seconds each plus a 30-second margin. The
timer is hourly and `Persistent=false`, so missed runs do not trigger a
catch-up acquisition after boot. No guessed memory, CPU, or disk limit is
included; limits require host measurements before they can be set responsibly.

## Later operator preflight

After the relevant host requirements are satisfied, validate substituted files as an unprivileged
operator before any enable/start decision. Confirm the checkout revision and
canonical BLS policies, the trusted retained-store ownership, the existing
shared-transport dependency and machine-local configuration, and that systemd
accepts the rendered units. A one-shot exit of `3` means scheduler recovery is
required; it must be investigated from retained claim/collector state, never
handled by changing this template into an automatic retry.

The collector’s 403/429 backoff and immutable claim/recovery semantics remain
inside the application. A systemd timer must not be treated as permission to
bypass them or as proof that a publisher request succeeded.

`scripts/render_bls_service.py --store <existing-absolute-store> --output
<existing-empty-absolute-directory> [--environment <private-local-file>]`
renders without installation or activation. It preserves a selected virtual
environment's interpreter path. Paths with whitespace, expansion syntax or
traversal are refused rather than escaped; choose plain absolute local paths.
Validate with `systemd-analyze --user verify <rendered-service> <rendered-timer>`.
Machine-local renderings and PATH configuration belong under ignored
`runs/local/`. On this WSL orchestrator, the service manager's default PATH
lacks Windows PowerShell/OpenSSH; a local environment file supplies those
directories without changing shared transport code or importing secrets into
tracked configuration. Local transient-service checks verified dependency
imports and Windows interoperability; these are not publisher observations.
