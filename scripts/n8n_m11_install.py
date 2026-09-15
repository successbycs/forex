#!/usr/bin/env python3
"""T480-local installer for the one fixed M11 n8n workflow.

This is deployment plumbing, not a scheduled collector.  It reads both the
n8n API key and PostgreSQL password only on the T480 and never prints them.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "Forex GDELT hourly download and stage": ROOT / "n8n" / "forex-gdelt-daily.json",
    "Forex GDELT hourly context import": ROOT / "n8n" / "forex-gdelt-hourly-import.json",
}
DERIVED_METRICS_MIGRATION = ROOT / "sql" / "migrations" / "024_m11_gdelt_derived_metrics.sql"
ARTICLE_RETENTION_MIGRATION = ROOT / "sql" / "migrations" / "025_m11_gdelt_article_retention.sql"
M13_SEED_NAME = "Forex M13 historical GDELT seed"
M13_SEED_WEBHOOK_ID = "31f35b0f-0b6e-4778-809f-14d13e8b0430"
LAB_ROOT = Path("/home/chris/projects/cs-ai-lab-infra")
KEY_FILE = Path("/home/chris/.config/cs-ai-lab/n8n-api-key")
NAME = "Forex GDELT hourly download and stage"
CREDENTIAL_NAME = "Forex M11 PostgreSQL"
LEGACY_WORKFLOW_NAME = "Forex GDELT daily H1 context ingestion"
GDELT_EGRESS_HEALTH_URL = "http://gdelt-egress:8092/healthz"
GDELT_N8N_ENV_FILE = Path("/home/chris/.config/forex/gdelt-n8n.env")
GDELT_EGRESS_SECRET_FILES = {
    "FOREX_GDELT_EGRESS_BEARER": Path("/home/chris/.config/forex/gdelt-egress-bearer"),
    "FOREX_GDELT_CANDIDATE_SIGNING_KEY": Path("/home/chris/.config/forex/gdelt-candidate-signing-key"),
}
GDELT_EGRESS_IMAGE = "forex-gdelt-publisher-egress:local"
GDELT_EGRESS_DOCKERFILE = ROOT / "deploy" / "gdelt" / "Dockerfile"
GDELT_EGRESS_BUILD_INPUTS = (
    ROOT / "src" / "forex" / "gdelt_publisher_egress.py",
    ROOT / "scripts" / "run_gdelt_publisher_egress.py",
    GDELT_EGRESS_DOCKERFILE,
)
GDELT_EGRESS_COMPOSE = ROOT / "deploy" / "gdelt" / "compose.yaml"
GDELT_N8N_COMPOSE_OVERRIDE = ROOT / "deploy" / "gdelt" / "compose.n8n.override.yaml"
GDELT_EGRESS_DIAGNOSTIC_LIMIT = 2_000


def env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (LAB_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _private_regular_text(path: Path, *, description: str) -> str:
    """Read one ignored local secret without following a link or relaxing mode."""
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(f"{description} must be an ordinary file")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise RuntimeError(f"{description} must be mode 0600")
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"{description} is unavailable") from exc


def require_private_gdelt_n8n_env(path: Path = GDELT_N8N_ENV_FILE,
                                  secret_files: dict[str, Path] = GDELT_EGRESS_SECRET_FILES) -> None:
    """Require the ignored, owner-only n8n credentials before activation.

    The bearer merely authenticates the n8n caller.  The independent HMAC key
    binds each public URL to the aggregate made by the fixed Code node.
    """
    try:
        raw = _private_regular_text(path, description="GDELT n8n environment")
        values = {
            key: value
            for line in raw.splitlines()
            if "=" in line and not line.lstrip().startswith("#")
            for key, value in [line.split("=", 1)]
        }
    except OSError as exc:
        raise RuntimeError("private GDELT n8n environment is unavailable") from exc
    required = ("FOREX_GDELT_EGRESS_BEARER", "FOREX_GDELT_CANDIDATE_SIGNING_KEY")
    if (set(values) != set(required) or any(len(values[key]) < 32 or any(char.isspace() for char in values[key]) for key in required)
            or values[required[0]] == values[required[1]]):
        raise RuntimeError("private GDELT n8n environment is invalid")
    for key in required:
        if key not in secret_files or _private_regular_text(secret_files[key], description=f"GDELT egress secret {key}") != values[key]:
            raise RuntimeError("private GDELT egress secrets do not match n8n environment")


def gdelt_egress_build_sha256(inputs: tuple[Path, ...] = GDELT_EGRESS_BUILD_INPUTS) -> str:
    """Hash exactly the files copied into the fixed egress container."""
    digest = hashlib.sha256()
    for path in inputs:
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("fixed GDELT egress build input is unavailable")
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_gdelt_egress_image() -> str:
    """Build from this repository root and prove Docker received this input."""
    build_sha256 = gdelt_egress_build_sha256()
    try:
        subprocess.run(
            ["docker", "build", "--pull=false", "--label", f"org.forex.gdelt.build-sha256={build_sha256}",
             "--tag", GDELT_EGRESS_IMAGE, "--file", str(GDELT_EGRESS_DOCKERFILE), str(ROOT)],
            check=True, capture_output=True, text=True,
        )
        inspected = subprocess.run(
            ["docker", "image", "inspect", "--format={{json .Config.Labels}}", GDELT_EGRESS_IMAGE],
            check=True, capture_output=True, text=True,
        )
        labels = json.loads(inspected.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise RuntimeError("fixed GDELT egress image build is unavailable") from exc
    if not isinstance(labels, dict) or labels.get("org.forex.gdelt.build-sha256") != build_sha256:
        raise RuntimeError("fixed GDELT egress image build proof is invalid")
    return build_sha256


def _compose_arguments(*arguments: str, egress: bool = False) -> list[str]:
    result = ["docker", "compose", "-f", str(LAB_ROOT / "compose.yaml")]
    if egress:
        result.extend(("-f", str(GDELT_EGRESS_COMPOSE), "-f", str(GDELT_N8N_COMPOSE_OVERRIDE)))
    return [*result, *arguments]


def _redact_egress_diagnostic(value: str) -> str:
    """Return a bounded, credential-free runtime diagnostic.

    The signed probe deliberately emits only HTTP/status facts.  Docker and
    Compose may nevertheless include environment assignments in errors, so do
    not trust their output unconditionally during a rollback.
    """
    redacted = value
    for name in ("FOREX_GDELT_EGRESS_BEARER", "FOREX_GDELT_CANDIDATE_SIGNING_KEY"):
        # Handles both ``NAME=value`` and JSON-ish ``\"NAME\": \"value\"``.
        redacted = re.sub(rf"({name}(?:=|[\"']\s*:\s*[\"']))[^\s\"']+", r"\1[REDACTED]", redacted)
    return " ".join(redacted.split())[:GDELT_EGRESS_DIAGNOSTIC_LIMIT] or "no diagnostic"


def _egress_rollback_diagnostic() -> str:
    """Collect only the bounded egress logs before its failure rollback."""
    try:
        result = subprocess.run(
            _compose_arguments("logs", "--no-color", "--tail", "50", "gdelt-egress", egress=True),
            cwd=LAB_ROOT, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "egress logs unavailable"
    return _redact_egress_diagnostic(" ".join(part for part in (result.stdout, result.stderr) if part))


def _verify_private_egress_topology() -> None:
    """Prove n8n has only Docker-internal networks after the merge."""
    try:
        n8n = subprocess.run(_compose_arguments("ps", "-q", "n8n", egress=True), cwd=LAB_ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        egress = subprocess.run(_compose_arguments("ps", "-q", "gdelt-egress", egress=True), cwd=LAB_ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        if not n8n or not egress:
            raise RuntimeError("missing fixed egress containers")
        network_names = json.loads(subprocess.run(
            ["docker", "inspect", "--format={{json .NetworkSettings.Networks}}", n8n],
            capture_output=True, text=True, check=True).stdout)
        egress_networks = json.loads(subprocess.run(
            ["docker", "inspect", "--format={{json .NetworkSettings.Networks}}", egress],
            capture_output=True, text=True, check=True).stdout)
        if not isinstance(network_names, dict) or not network_names:
            raise RuntimeError("n8n network inspection is invalid")
        if not isinstance(egress_networks, dict) or len(egress_networks) != 2:
            raise RuntimeError("egress network inspection is invalid")
        for name in network_names:
            inspected = json.loads(subprocess.run(["docker", "network", "inspect", "--format={{json .Internal}}", name],
                                                  capture_output=True, text=True, check=True).stdout)
            if inspected is not True:
                raise RuntimeError("n8n retains an outbound network")
        internal_count = 0
        for name in egress_networks:
            inspected = json.loads(subprocess.run(["docker", "network", "inspect", "--format={{json .Internal}}", name],
                                                  capture_output=True, text=True, check=True).stdout)
            internal_count += int(inspected is True)
        if internal_count != 1:
            raise RuntimeError("egress must have exactly one private caller network")
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise RuntimeError("private GDELT egress topology is unavailable") from exc


def apply_gdelt_egress_compose() -> None:
    """Apply egress + n8n as one bounded operation; restore base n8n on failure."""
    for path in (GDELT_EGRESS_COMPOSE, GDELT_N8N_COMPOSE_OVERRIDE):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError("fixed GDELT egress compose contract is unavailable")
    applied = False
    try:
        subprocess.run(_compose_arguments("config", "--quiet", egress=True), cwd=LAB_ROOT, check=True,
                       capture_output=True, text=True)
        subprocess.run(_compose_arguments("up", "-d", "--no-deps", "gdelt-egress", egress=True), cwd=LAB_ROOT,
                       check=True, capture_output=True, text=True)
        applied = True
        subprocess.run(_compose_arguments("up", "-d", "--no-deps", "--force-recreate", "n8n", egress=True),
                       cwd=LAB_ROOT, check=True, capture_output=True, text=True)
        _verify_private_egress_topology()
        require_gdelt_egress()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        rollback_diagnostic = "egress was not started"
        if applied:
            # Take this before removal. Handler logs are intentionally quiet
            # on success; on a failed health probe this is the only service
            # level evidence that survives the rollback.
            rollback_diagnostic = _egress_rollback_diagnostic()
            # Restore n8n's preceding shared-compose topology and remove only
            # this dedicated service. No database, workflow, or evidence data
            # is deleted by this rollback.
            subprocess.run(_compose_arguments("up", "-d", "--no-deps", "--force-recreate", "n8n"), cwd=LAB_ROOT,
                           capture_output=True, text=True, check=False)
            subprocess.run(_compose_arguments("rm", "-sf", "gdelt-egress", egress=True), cwd=LAB_ROOT,
                           capture_output=True, text=True, check=False)
        cause = _redact_egress_diagnostic(str(exc))
        raise RuntimeError(
            "bounded GDELT publisher egress installation failed and was rolled back: "
            f"cause={cause}; egress_logs={rollback_diagnostic}"
        ) from exc


def api(method: str, path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    request = Request(
        "http://127.0.0.1:5678/api/v1" + path, body, method=method,
        headers={"accept": "application/json", "content-type": "application/json", "X-N8N-API-KEY": KEY_FILE.read_text().strip()},
    )
    try:
        with urlopen(request, timeout=60) as response:
            value = json.loads(response.read())
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"n8n {method} {path} failed with HTTP {error.code}: {detail}") from error
    if not isinstance(value, dict):
        raise RuntimeError("n8n returned an invalid response")
    return value


def upsert_workflow(name: str, payload: dict) -> dict:
    workflows = api("GET", "/workflows?limit=250").get("data", [])
    existing = next((item for item in workflows if item.get("name") == name), None)
    if existing and existing.get("active"):
        api("POST", f"/workflows/{existing['id']}/deactivate")
    return api("PUT", f"/workflows/{existing['id']}", payload) if existing else api("POST", "/workflows", payload)


def deactivate_legacy_workflow() -> None:
    """Remove only the known obsolete webhook owner before activating M11-R1."""
    workflows = api("GET", "/workflows?limit=250").get("data", [])
    legacy = next((item for item in workflows if item.get("name") == LEGACY_WORKFLOW_NAME), None)
    if legacy and legacy.get("active"):
        api("POST", f"/workflows/{legacy['id']}/deactivate")


def activate_workflow(workflow_id: str) -> None:
    api("POST", f"/workflows/{workflow_id}/activate")


def payload_for(workflow: dict, credential_id: str) -> dict:
    """Bind the one fixed credential; no caller selects workflows or SQL."""
    for node in workflow["nodes"]:
        if node.get("id") in {"stage", "persist-hourly-context", "import-staged-hour"}:
            node["credentials"] = {"postgres": {"id": credential_id, "name": CREDENTIAL_NAME}}
    return {key: workflow.get(key, {} if key in {"connections", "settings"} else []) for key in ("name", "nodes", "connections", "settings")}


def apply_gdelt_migrations() -> None:
    """Apply only the fixed additive GDELT migrations before workflow import."""
    migrations = (DERIVED_METRICS_MIGRATION, ARTICLE_RETENTION_MIGRATION)
    if any(not migration.is_file() or migration.is_symlink() for migration in migrations):
        raise RuntimeError("fixed GDELT migration is unavailable")
    subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "cs_ai_lab", "-d", "cs_ai_lab"],
        cwd=LAB_ROOT,
        input="\n".join(migration.read_text(encoding="utf-8") for migration in migrations),
        check=True,
        capture_output=True,
        text=True,
    )


def require_gdelt_egress() -> None:
    """Fail closed from n8n with an authenticated, signed, no-network request."""
    # A valid signed localhost candidate must be rejected by the egress URL
    # policy before DNS or any publisher connection.  It proves both n8n
    # secrets match the egress secrets without exposing either value.
    # Use Node's stable ``http`` built-in rather than global ``fetch``. Some
    # otherwise supported n8n images predate global fetch; a missing API must
    # not look indistinguishable from an egress/network fault. The emitted
    # result has only fixed status facts, never headers or secret material.
    probe = """const crypto=require('crypto'),http=require('http');const bearer=process.env.FOREX_GDELT_EGRESS_BEARER,key=process.env.FOREX_GDELT_CANDIDATE_SIGNING_KEY;const emit=v=>console.log(JSON.stringify(v));if(!bearer||!key||bearer.length<32||key.length<32||bearer===key){emit({probe:'GDELT_EGRESS_CONTRACT_V1',valid:false,reason:'N8N_SECRET_ENV_INVALID'});process.exit(1)}const candidate={canonical_url:'https://localhost/forex-egress-contract',sources:[{source_observation_id:'gdelt-egress-contract-check',gdelt_document_id:'contract-check',bucket_time_utc:'2026-01-01T00:00:00Z',source_tone:null}]},material={aggregate_sha256:'sha256:'+'a'.repeat(64),bucket_time_utc:'2026-01-01T00:00:00Z',candidate},stable=v=>Array.isArray(v)?'['+v.map(stable).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+stable(v[k])).join(',')+'}':JSON.stringify(v),request={...material,signature:crypto.createHmac('sha256',key).update(stable(material),'utf8').digest('hex')},bad={...request,signature:'0'.repeat(64)},call=(path,body)=>new Promise(resolve=>{const raw=body?JSON.stringify(body):'';const req=http.request({host:'gdelt-egress',port:8092,path,method:body?'POST':'GET',headers:body?{Authorization:'Bearer '+bearer,'Content-Type':'application/json','Content-Length':Buffer.byteLength(raw)}:{}},res=>{let data='';res.setEncoding('utf8');res.on('data',part=>{if(data.length<512)data+=part});res.on('end',()=>{let parsed={};try{parsed=JSON.parse(data)}catch{}resolve({transport:'OK',http_status:res.statusCode,status:parsed.status||null,reason:parsed.reason||null})})});req.setTimeout(5000,()=>req.destroy(new Error('TIMEOUT')));req.on('error',error=>resolve({transport:'ERROR',error:error.code==='ETIMEDOUT'?'TIMEOUT':'REQUEST_ERROR'}));if(body)req.write(raw);req.end()});Promise.all([call('/healthz'),call('/forex/gdelt/fetch',request),call('/forex/gdelt/fetch',bad)]).then(([health,accepted,mismatch])=>{const valid=health.transport==='OK'&&health.http_status===200&&health.status==='OK'&&accepted.transport==='OK'&&accepted.http_status===200&&accepted.status==='FAILED'&&accepted.reason==='REFUSED_HOST'&&mismatch.transport==='OK'&&mismatch.http_status===200&&mismatch.status==='FAILED'&&mismatch.reason==='REFUSED_SIGNATURE';emit({probe:'GDELT_EGRESS_CONTRACT_V1',valid,health,accepted,mismatch});process.exitCode=valid?0:1}).catch(()=>{emit({probe:'GDELT_EGRESS_CONTRACT_V1',valid:false,reason:'PROBE_INTERNAL_ERROR'});process.exitCode=1});"""
    try:
        result = subprocess.run(
            _compose_arguments("exec", "-T", "n8n", "node", "-e", probe, egress=True),
            cwd=LAB_ROOT, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("bounded GDELT publisher egress is unavailable") from exc
    if result.returncode != 0:
        # The probe never writes secrets; retain only its bounded diagnostic so
        # an installation rollback can be repaired from evidence rather than
        # retried blindly.
        diagnostic = _redact_egress_diagnostic(
            " ".join(part for part in (result.stdout, result.stderr) if part)
        )
        raise RuntimeError(f"bounded GDELT publisher egress health contract is invalid: {diagnostic}")


def m13_historical_seed(workflow: dict) -> dict:
    """Derive one non-scheduled, fixed M13 seed from the proven M11 stage flow."""
    seed = json.loads(json.dumps(workflow))
    seed["name"] = M13_SEED_NAME
    seed["nodes"] = [node for node in seed["nodes"] if node.get("id") != "schedule"]
    for node in seed["nodes"]:
        if node.get("id") == "webhook":
            node["name"] = "Run fixed M13 historical seed (T480-local only)"
            node["webhookId"] = M13_SEED_WEBHOOK_ID
            node["parameters"]["path"] = "forex-m13-historical-context-seed"
        elif node.get("id") == "build":
            node["name"] = "Build four fixed historical GKG URLs"
            node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace(
                "const n=new Date(),h=new Date(Date.UTC(n.getUTCFullYear(),n.getUTCMonth(),n.getUTCDate(),n.getUTCHours()-1));",
                "const h=new Date('2026-08-28T00:00:00Z');",
            )
    seed["connections"].pop("Schedule after UTC hour closes", None)
    seed["connections"]["Run fixed M13 historical seed (T480-local only)"] = seed["connections"].pop(
        "Run M11 now (T480-local only)"
    )
    seed["connections"]["Run fixed M13 historical seed (T480-local only)"]["main"][0][0]["node"] = (
        "Build four fixed historical GKG URLs"
    )
    seed["connections"]["Build four fixed historical GKG URLs"] = seed["connections"].pop(
        "Build four closed-hour GKG URLs"
    )
    return seed


def main() -> None:
    workflows = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in WORKFLOWS.items()}
    if any(item.get("name") != name or item.get("active") is not False for name, item in workflows.items()):
        raise RuntimeError("fixed M11 workflow contract is invalid")
    require_private_gdelt_n8n_env()
    build_gdelt_egress_image()
    apply_gdelt_migrations()
    apply_gdelt_egress_compose()
    lookup = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "cs_ai_lab", "-d", "cs_ai_lab", "-Atqc", "SELECT id FROM credentials_entity WHERE name = 'Forex M11 PostgreSQL' AND type = 'postgres' LIMIT 1"],
        cwd=LAB_ROOT, check=True, capture_output=True, text=True,
    )
    credential_id = lookup.stdout.strip()
    if not credential_id:
        values = env_file()
        credential = api("POST", "/credentials", {"name": CREDENTIAL_NAME, "type": "postgres", "data": {"host": "postgres", "port": 5432, "database": values["POSTGRES_DB"], "user": values["POSTGRES_USER"], "password": values["POSTGRES_PASSWORD"], "ssl": "disable", "sshTunnel": False}})
        credential_id = str(credential.get("id") or "")
    if not credential_id:
        raise RuntimeError("n8n PostgreSQL credential was not created")
    ids = {}
    for name, workflow in workflows.items():
        response = upsert_workflow(name, payload_for(workflow, credential_id))
        if not (workflow_id := str(response.get("id") or "")):
            raise RuntimeError(f"n8n M11 workflow was not created: {name}")
        ids[name] = workflow_id
    for workflow_id in ids.values():
        activate_workflow(workflow_id)
    print(json.dumps({"workflow_id": ids[NAME], "workflow_name": NAME, "workflow_ids": ids, "credential_configured": True, "activated": True, "ok": True}))


if __name__ == "__main__":
    main()
