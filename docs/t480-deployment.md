# T480 deployment transport constraint

Every T480 deployment must treat the remote command-length limit as a hard
transport boundary. The T480 SSH endpoint expands a PowerShell command before
Windows executes it and rejects a command that is too long. The observed safe
envelope for a fully encoded SSH command is fewer than 7,500 characters. A
local command that appears short can exceed that limit after encoding.

Before any T480 deployment, read this document and run the adapter transport
limit tests. A candidate deployment is `NO-GO` if any fixed non-fragment
operation exceeds the envelope. Do not retry a failed long command, widen the
transport limit, or use a generic remote shell or file-copy workaround.

Large reviewed payloads must use the fixed adapter's numbered Base64 fragments.
Each payload is reassembled and SHA-256 verified on T480 before `prepare` can
bind a release, and `install` refuses an unprepared release. Small operational
launchers must run from an already hash-bound ProgramData payload rather than
embedding a full Python environment or script in the SSH command. The M30 Demo
execution drill follows this rule: the adapter only creates its narrow lock and
starts the released listener payload; that payload launches the released
runner.

If a deployment encounters `The command line is too long`, no broker action or
release installation has occurred. Stop at the failed operation, retain the
result, shorten the fixed operation or move its logic into a hash-bound
payload, add a regression test against the encoded command length, then stage
and verify a new release. The existing listener must not be put on maintenance
hold solely to repair transport length.
