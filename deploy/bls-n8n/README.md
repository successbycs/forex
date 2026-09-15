# BLS n8n retention deployment

Prepared application package, not an installed service. The workflow is manual
and inactive. It does not replace the existing BLS scheduler or GDELT jobs.
Do not add a recurring trigger until BLS claim/backoff policy is integrated;
manual execution is not permission to bypass an outstanding source backoff.

## Deployment gates

Chris has authorised execution of the A1 ExecPlan. Shared infrastructure's
`docs/project-foundation.md` also holds new services pending physical disk and
representative resource measurements. Linux virtual free space does not clear
that hold. Preserve the existing shared stack, networking and credentials.
Deployment awaits this capacity clearance; local tests do not satisfy it.

The fixed adapter is `scripts/a1_t480_deploy.py`. It creates a deterministic
package that contains only the A1 service, its exact Python dependency closure,
the reviewed Docker files, and the inactive workflow export. It accepts no
caller-selected shell command, Docker image, path, port, URL, or source file.
After representative measurements select limits, run:

    python3 scripts/a1_t480_deploy.py package
    python3 scripts/a1_t480_deploy.py inspect
    python3 scripts/a1_t480_deploy.py deploy --approve --cpu 0.25 --memory-mib 128 --pids 64

The last command is the only mutating adapter operation. It makes the bearer
token on T480 in a mode-0600 file and never returns it. If the fixed service
name already exists, it returns that container's status and makes no change.

Both the archive and generated deployment program are staged at fixed private
paths in 512-byte chunks. Every chunk verifies its SHA-256 and expected append
offset; final hashes are checked before rename and before program execution.
All shared-transport commands, including setup and invocation, are checked
against a conservative 7,500-character complete Windows command budget.
This accounts for the smaller Windows SSH shell hop: on 2026-09-14 a read-only
1,024-byte probe succeeded (8,343 outer command characters), while a 4,096-byte
probe failed (22,903 characters) with `The command line is too long.` The
32,767-character process limit alone did not protect that hop. The full
deployment program is executed locally within T480 WSL after verified staging,
so its contents never become one large Windows command argument.

On 2026-09-14, read-only inspection found n8n 1.123.76 in container
`cs-ai-lab-n8n-1` on network `cs-ai-lab_internal`, with no service answering
at its loopback port 8091. The retention container must share **n8n's network
namespace**, using `--network container:cs-ai-lab-n8n-1`. Then the workflow's
`http://127.0.0.1:8091/forex/a1/retain-bls` reaches retention without opening a
host/public port. Host loopback or an ordinary separate container will not work.
If the n8n container is recreated, recreate the retention container against the
new namespace. Do not restart n8n solely to install retention.

## Prepare after gate clearance

Use the reviewed Forex checkout as Docker build context. Select a Python 3.11+
base image by immutable digest and record that digest and the resulting image
ID with the reviewed source hashes. This standard-library-only service does
not need database, SSH, broker, or Docker credentials.

    docker build --build-arg PYTHON_IMAGE=python@sha256:<reviewed-digest> -f deploy/bls-n8n/Dockerfile -t forex-bls-retention:<reviewed-source-id> .

Import `n8n/forex-bls-calendar-retention.json` as a new, inactive workflow;
never overwrite a GDELT workflow. Create an n8n HTTP Header Auth credential
whose header name is `Authorization` and value is `Bearer <private-token>`.
Generate at least 32 random token characters outside tracked files; do not
place it in workflow JSON, command output or execution logs. Bind that
credential to the `Retain BLS` node. Record the assigned workflow ID and hash
the exported configured definition. The service binding is operator-provided,
not an independently authenticated n8n execution identity.

Create a mode-0600 environment file outside Git containing:

    FOREX_BLS_N8N_BIND_HOST=127.0.0.1
    FOREX_BLS_N8N_PORT=8091
    FOREX_BLS_N8N_STORE=/data
    FOREX_BLS_N8N_HANDOFF_TOKEN=<same-private-token>
    FOREX_BLS_N8N_WORKFLOW_ID=<assigned-id>
    FOREX_BLS_N8N_WORKFLOW_SHA256=sha256:<configured-definition-digest>

Create a dedicated retained-store directory owned by UID/GID 65532. Supply
its absolute path and the environment file path in this command; placeholders
must be replaced and checked before execution. Do not mount the Docker socket,
shared database data, another product's store, or the user's home directory.

Before running the service, record CPU, memory and process-ID limits from the
shared platform's representative headroom evidence. Do not guess them from the
48 MB image or the local smoke test. Include the reviewed values below; these
limits are part of deployment acceptance.

    docker run -d --name forex-bls-retention --network container:cs-ai-lab-n8n-1 --read-only --cap-drop ALL --security-opt no-new-privileges --cpus <reviewed-cpu-limit> --memory <reviewed-memory-limit> --pids-limit <reviewed-pids-limit> --env-file <private-env-file> --mount type=bind,src=<dedicated-store>,dst=/data forex-bls-retention:<reviewed-source-id>

No restart policy is enabled initially. Check `/healthz` from inside n8n,
then execute one approved manual capture. A successful handoff returns
`RETAINED` with observation and receipt hashes. A malformed/unauthenticated
handoff must be refused without creating evidence. Exact retries preserve
bytes; conflicting reuse of a capture ID must be refused.

## Verification and rollback

The deployer records private transaction intent before creating an n8n
credential and saves each returned object ID before its next API call. A failed
request may have succeeded remotely even when its response was lost. If
`deployment-state.json` exists, retries refuse to create further credentials or
workflows. Preserve that file and reconcile the recorded phase and IDs with n8n
before recovery; do not delete it merely to retry. A failed setup may require
reconciling an object whose ID was never returned. This adapter does not yet
automate that recovery.

Keep the raw store unchanged and take a stable copy to the Forex orchestrator
for independent receipt verification and the existing fixed PostgreSQL
projection path. Database credentials are never supplied to this service.
Follow the A1 plan's concrete commands for verification, projection and report.
Do not insert sample records to make the report pass.

Retention establishes integrity of an authenticated client's submitted bytes;
it does not independently authenticate the publisher, workflow execution or
client timestamps. Retain actual n8n execution observations separately before
claiming an operational n8n outcome. Never describe these receipts as the
existing shared-transport receipt format.

To roll back, leave the new workflow inactive and stop only
`forex-bls-retention`. Preserve the retained store, environment file and
configured workflow export for diagnosis. Do not delete raw bytes, drop tables,
stop GDELT workflows, or restore a shared-stack snapshot. Starting/stopping this
application never changes M29 status or grants trading authority.

The HTTP node shape was checked against the installed version's
[n8n HTTP implementation](https://github.com/n8n-io/n8n/blob/n8n%401.123.76/packages/nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts):
full file responses retain status/headers; disabling redirects requires
`options.redirect.redirect.followRedirects=false`. The 2 MiB handoff check
runs after n8n downloads the file, not as a streaming download limit.
