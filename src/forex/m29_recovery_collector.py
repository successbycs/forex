"""Fail-closed, local evidence collection for the M29 held listener drill.

This module deliberately has no transport, MT5, task-scheduler, or order
capability.  A separately authorised operator captures responses from the
fixed T480 operations and supplies their *raw adapter envelopes* here.  The
collector stores those bytes exactly once, then verifies their relationships
from the retained bytes.  It therefore cannot turn a synthetic or incomplete
observation into a real-world M29 closeout.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "forex.m29.recovery-collector.v1"
MANIFEST_SCHEMA = "forex.m29.recovery-collector-manifest.v1"
OUTCOME_READY = "READY_FOR_FRESH_DEMO_DRILL"
OUTCOME_CAPTURED = "RECOVERY_DRILL_CAPTURED_NOT_M29_PROVEN"
_RELEASE = re.compile(r"[0-9a-f]{16}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_ROLES = {
    "preflight-listener": "m20_listener_status",
    "preflight-diagnostics": "m20_listener_diagnostics",
    "preflight-spool-page": "m20_listener_spool_page",
    "continuity-status": "m20_listener_continuity_status",
    "postflight-listener": "m20_listener_status",
    "postflight-diagnostics": "m20_listener_diagnostics",
    "postflight-spool-page": "m20_listener_spool_page",
}


class RecoveryCollectorError(ValueError):
    """A proposed evidence bundle is incomplete, tampered, or ambiguous."""


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RecoveryCollectorError("duplicate JSON field")
        result[key] = value
    return result


def _json(raw: bytes, *, label: str) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(RecoveryCollectorError("nonfinite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise RecoveryCollectorError(f"{label} is not valid JSON") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise RecoveryCollectorError(f"{label} timestamp is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RecoveryCollectorError(f"{label} timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise RecoveryCollectorError(f"{label} timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _stdout(raw: bytes, *, role: str) -> dict[str, Any]:
    outer = _json(raw, label=role)
    expected = _ROLES[role]
    if not isinstance(outer, dict) or outer.get("operation") != expected or outer.get("ok") is not True:
        raise RecoveryCollectorError(f"{role} is not a successful fixed {expected} envelope")
    result = outer.get("result")
    if not isinstance(result, dict) or result.get("ok") is not True or result.get("exit_code") != 0:
        raise RecoveryCollectorError(f"{role} fixed operation failed")
    stdout = result.get("stdout")
    if not isinstance(stdout, str):
        raise RecoveryCollectorError(f"{role} has no fixed operation output")
    value = _json(stdout.encode("utf-8"), label=f"{role} output")
    if not isinstance(value, dict):
        raise RecoveryCollectorError(f"{role} output is not an object")
    return value


def _release(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _RELEASE.fullmatch(value) is None:
        raise RecoveryCollectorError(f"{label} listener release is invalid")
    return value


def _listener(value: dict[str, Any], *, role: str) -> tuple[str, datetime]:
    release = _release(value.get("release_id"), label=role)
    if value.get("running") is not True or value.get("state") != "MAINTENANCE_HOLD":
        raise RecoveryCollectorError(f"{role} does not show a running maintenance-held listener")
    heartbeat = _utc(value.get("heartbeat_at_utc"), label=role)
    monitor = value.get("monitor")
    if not isinstance(monitor, dict) or monitor.get("state") != "IDLE":
        raise RecoveryCollectorError(f"{role} does not show an idle monitor")
    return release, heartbeat


def _diagnostics(value: dict[str, Any], *, role: str, release: str) -> tuple[str, str]:
    if value.get("maintenance_hold_present") is not True or value.get("logon_type") != "S4U":
        raise RecoveryCollectorError(f"{role} does not preserve held S4U listener identity")
    binding = value.get("deployment_binding")
    if not isinstance(binding, dict) or binding.get("observation") != "VALID":
        raise RecoveryCollectorError(f"{role} deployment binding is unavailable")
    fingerprint = binding.get("configuration_fingerprint")
    revision = binding.get("application_revision")
    lease = binding.get("lease")
    if (not isinstance(fingerprint, str) or not _DIGEST.fullmatch(fingerprint)
            or not isinstance(revision, str) or not revision
            or not isinstance(lease, dict) or lease.get("server") != "GOMarketsMU-Demo"
            or lease.get("symbol") != "EURUSD"):
        raise RecoveryCollectorError(f"{role} deployment binding is unsafe")
    # Diagnostics does not carry release_id itself; the paired listener binds it.
    if _RELEASE.fullmatch(release) is None:
        raise RecoveryCollectorError(f"{role} listener release is invalid")
    return fingerprint, revision


def _page(value: dict[str, Any], *, role: str, release: str) -> tuple[int, list[tuple[int, str]]]:
    if _release(value.get("listener_release_id"), label=role) != release:
        raise RecoveryCollectorError(f"{role} release differs from listener")
    after = value.get("after_assessment_sequence")
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise RecoveryCollectorError(f"{role} cursor is invalid")
    records = value.get("records")
    if not isinstance(records, list) or len(records) > 8:
        raise RecoveryCollectorError(f"{role} records are invalid")
    if value.get("observation") == "SPOOL_ABSENT":
        if records:
            raise RecoveryCollectorError(f"{role} absent spool has records")
        return after, []
    if value.get("observation") != "AVAILABLE":
        raise RecoveryCollectorError(f"{role} spool observation is unsupported")
    result: list[tuple[int, str]] = []
    previous = after
    for index, row in enumerate(records):
        if not isinstance(row, dict) or set(row) != {"assessment_sequence", "raw_sha256", "raw_base64"}:
            raise RecoveryCollectorError(f"{role} spool record shape is invalid")
        sequence, digest = row["assessment_sequence"], row["raw_sha256"]
        if (isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0
                or not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None):
            raise RecoveryCollectorError(f"{role} spool receipt identity is invalid")
        if index and sequence != previous + 1:
            raise RecoveryCollectorError(f"{role} spool sequence has a gap")
        if not index and after > 0 and sequence != after + 1:
            raise RecoveryCollectorError(f"{role} spool does not continue its cursor")
        encoded = row["raw_base64"]
        if not isinstance(encoded, str):
            raise RecoveryCollectorError(f"{role} spool source is not base64")
        try:
            source = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise RecoveryCollectorError(f"{role} spool source is not base64") from exc
        if _sha(source) != digest:
            raise RecoveryCollectorError(f"{role} spool source hash mismatch")
        source_record = _json(source, label=f"{role} spool source")
        if (not isinstance(source_record, dict) or source_record.get("listener_release_id") != release
                or source_record.get("assessment_sequence") != sequence):
            raise RecoveryCollectorError(f"{role} spool source receipt binding is invalid")
        result.append((sequence, digest))
        previous = sequence
    return after, result


def inspect(envelopes: Mapping[str, bytes]) -> dict[str, Any]:
    """Validate fixed observations and return only bounded, non-secret facts.

    A PASS continuity record becomes a *captured drill observation*, not M29
    proof: freshness, repository/current-config binding, raw event-log export,
    and the independent M29 verifier remain required at closeout time.
    """
    if set(envelopes) != set(_ROLES):
        raise RecoveryCollectorError("recovery collector requires the exact fixed observation set")
    output = {role: _stdout(raw, role=role) for role, raw in envelopes.items()}
    pre_release, pre_heartbeat = _listener(output["preflight-listener"], role="preflight-listener")
    post_release, post_heartbeat = _listener(output["postflight-listener"], role="postflight-listener")
    if pre_release != post_release:
        raise RecoveryCollectorError("listener release changed across recovery drill")
    if post_heartbeat <= pre_heartbeat:
        raise RecoveryCollectorError("postflight heartbeat is not later than preflight heartbeat")
    pre_binding = _diagnostics(output["preflight-diagnostics"], role="preflight-diagnostics", release=pre_release)
    post_binding = _diagnostics(output["postflight-diagnostics"], role="postflight-diagnostics", release=pre_release)
    if pre_binding != post_binding:
        raise RecoveryCollectorError("deployment binding changed across recovery drill")
    pre_after, pre_receipts = _page(output["preflight-spool-page"], role="preflight-spool-page", release=pre_release)
    post_after, post_receipts = _page(output["postflight-spool-page"], role="postflight-spool-page", release=pre_release)
    pre_last = pre_receipts[-1][0] if pre_receipts else pre_after
    if post_after != pre_last:
        raise RecoveryCollectorError("postflight spool cursor does not bind preflight receipt")
    identities = pre_receipts + post_receipts
    if len({sequence for sequence, _ in identities}) != len(identities):
        raise RecoveryCollectorError("duplicate assessment receipt sequence observed")
    continuity = output["continuity-status"]
    record = continuity.get("record")
    if continuity.get("observation") != "AVAILABLE" or not isinstance(record, dict):
        raise RecoveryCollectorError("continuity protocol record is unavailable")
    if (record.get("schema_version") != "forex.m20.continuity-protocol.v1" or record.get("state") != "PASS"
            or record.get("release_id") != pre_release or not isinstance(record.get("run_id"), str)
            or not isinstance(record.get("handoff"), dict) or record["handoff"].get("state") != "RECOVERED"
            or record.get("broker_mutation") not in (None, "NONE")):
        raise RecoveryCollectorError("continuity protocol does not show a bounded recovered no-order handoff")
    event_hash = continuity.get("event_log_sha256")
    if not isinstance(event_hash, str) or _DIGEST.fullmatch(event_hash) is None:
        raise RecoveryCollectorError("continuity protocol event-log receipt is absent")
    if continuity.get("logon_type") != "S4U":
        raise RecoveryCollectorError("continuity protocol task identity is unsafe")
    return {
        "schema_version": SCHEMA,
        "state": OUTCOME_CAPTURED,
        "execution_authority": False,
        "listener_release_id": pre_release,
        "configuration_fingerprint": pre_binding[0],
        "application_revision": pre_binding[1],
        "continuity_run_id": record["run_id"],
        "continuity_event_log_sha256": event_hash,
        "preflight_heartbeat_at_utc": pre_heartbeat.isoformat().replace("+00:00", "Z"),
        "postflight_heartbeat_at_utc": post_heartbeat.isoformat().replace("+00:00", "Z"),
        "receipt_identities": [{"assessment_sequence": seq, "raw_sha256": digest} for seq, digest in identities],
        "limitations": [
            "Not M29 proof: this local collector does not execute the drill or establish current freshness.",
            "Not M29 proof: current repository/configuration binding and independent contract verification remain required.",
            "Not M29 proof: the retained continuity event-log bytes require a declared fixed export before closeout.",
        ],
    }


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def collect(*, evidence_root: Path, run_id: str, envelopes: Mapping[str, bytes]) -> dict[str, Any]:
    """Append an exact raw capture and local manifest beneath a trusted root."""
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id) is None:
        raise RecoveryCollectorError("run ID is invalid")
    if evidence_root.is_symlink() or not evidence_root.is_dir():
        raise RecoveryCollectorError("evidence root must be a trusted existing directory")
    target = evidence_root / run_id
    if target.exists() or target.is_symlink():
        raise RecoveryCollectorError("recovery evidence run already exists")
    facts = inspect(envelopes)
    target.mkdir(mode=0o700)
    try:
        artifacts = []
        for role in sorted(_ROLES):
            name = role + ".json"
            raw = envelopes[role]
            _write_new(target / name, raw)
            artifacts.append({"path": name, "sha256": _sha(raw)})
        result_raw = (json.dumps(facts, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        _write_new(target / "collector-result.json", result_raw)
        artifacts.append({"path": "collector-result.json", "sha256": _sha(result_raw)})
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "run_id": run_id,
            "state": OUTCOME_CAPTURED,
            "execution_authority": False,
            "artifacts": artifacts,
        }
        _write_new(target / "manifest.json", (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    except BaseException:
        # Preserve any partial capture for investigation; never repair/delete it.
        raise
    return {**facts, "bundle": str(target)}


def verify(*, bundle: Path) -> dict[str, Any]:
    """Independently verify a collector bundle using only its retained bytes."""
    if bundle.is_symlink() or not bundle.is_dir():
        raise RecoveryCollectorError("bundle must be a regular directory")
    manifest_path = bundle / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RecoveryCollectorError("collector manifest is absent")
    manifest = _json(manifest_path.read_bytes(), label="collector manifest")
    if (not isinstance(manifest, dict) or set(manifest) != {"schema_version", "run_id", "state", "execution_authority", "artifacts"}
            or manifest.get("schema_version") != MANIFEST_SCHEMA
            or manifest.get("state") != OUTCOME_CAPTURED or manifest.get("execution_authority") is not False):
        raise RecoveryCollectorError("collector manifest is invalid")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id) is None:
        raise RecoveryCollectorError("collector manifest run ID is invalid")
    artifacts = manifest.get("artifacts")
    expected_names = {role + ".json" for role in _ROLES} | {"collector-result.json"}
    if (not isinstance(artifacts, list) or len(artifacts) != len(expected_names)
            or {entry.get("path") for entry in artifacts if isinstance(entry, dict)} != expected_names):
        raise RecoveryCollectorError("collector manifest artifact set is invalid")
    if {path.name for path in bundle.iterdir() if path.is_file()} != expected_names | {"manifest.json"}:
        raise RecoveryCollectorError("collector bundle contains missing or unexpected files")
    raw: dict[str, bytes] = {}
    for entry in artifacts:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise RecoveryCollectorError("collector manifest artifact is invalid")
        name, digest = entry["path"], entry["sha256"]
        path = bundle / name
        if (not isinstance(name, str) or Path(name).name != name or path.is_symlink() or not path.is_file()
                or not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None or _sha(path.read_bytes()) != digest):
            raise RecoveryCollectorError("collector artifact hash mismatch")
        if name.endswith(".json") and name != "collector-result.json":
            raw[name[:-5]] = path.read_bytes()
    observed = inspect(raw)
    retained = _json((bundle / "collector-result.json").read_bytes(), label="collector result")
    if retained != observed:
        raise RecoveryCollectorError("collector result does not bind retained evidence")
    return {"schema_version": SCHEMA, "state": OUTCOME_CAPTURED, "verified": True,
            "execution_authority": False, "continuity_run_id": observed["continuity_run_id"]}
