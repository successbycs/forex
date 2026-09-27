"""Fixed, read-only Release-A candidate collector for the M33 MT5 observer.

This payload only reports whether a separately provisioned observer task has
the shape required for a later binding release.  It cannot create a task,
read a credential, start/stop a process, connect to MT5, or submit an order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TASK_NAME = "CS AI Lab MT5 Observer"
SCHEMA = "forex.trading-health-mt5-observer-candidate.v1"
RECEIPT_SCHEMA = "forex.trading-health-mt5-observer-bootstrap-receipt.v1"
REFUSAL_SCHEMA = "forex.trading-health-mt5-observer-bootstrap-refusal.v1"
ADMINISTRATORS_SID = "S-1-5-32-544"
SYSTEM_SID = "S-1-5-18"
SID_RE = re.compile(r"^S-[0-9]+(?:-[0-9]+)+$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REFUSAL_REASONS = frozenset({
    "ACL_ACE_INVALID", "ACL_ADMIN_SYSTEM_REQUIRED", "ACL_OWNER_OR_INHERITANCE_INVALID",
    "ACL_SHAPE_INVALID", "DUPLICATE_JSON_FIELD", "NONFINITE_JSON", "OBSERVATION_FIELDS_INVALID",
    "OBSERVATION_INVALID", "OBSERVATION_IO_FAILED", "OBSERVATION_JSON_INVALID",
    "OBSERVATION_NOT_OBJECT", "OBSERVER_PRINCIPAL_PRIVILEGED", "RELEASE_DIGEST_INVALID",
    "STATE_ROOT_MISMATCH", "TASK_ACTION_NOT_FIXED_PORTABLE", "TASK_NOT_S4U", "TASK_OR_IDENTITY_INVALID",
    "WINDOWS_FIXED_OBSERVATION_FAILED", "WINDOWS_FIXED_OBSERVATION_REQUIRED",
})


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ValueError("NONFINITE_JSON")


def _parse(raw: str) -> dict[str, Any]:
    value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    if not isinstance(value, dict):
        raise ValueError("OBSERVATION_NOT_OBJECT")
    return value


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _acl(raw: Any, *, observer_sid: str, location: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != {"owner_sid", "inheritance", "aces"}:
        raise ValueError("ACL_SHAPE_INVALID")
    owner, inherited, aces = raw["owner_sid"], raw["inheritance"], raw["aces"]
    if owner != ADMINISTRATORS_SID or inherited is not False or not isinstance(aces, list):
        raise ValueError("ACL_OWNER_OR_INHERITANCE_INVALID")
    normalized: list[tuple[str, str]] = []
    for ace in aces:
        if not isinstance(ace, dict) or set(ace) != {"sid", "rights", "type"}:
            raise ValueError("ACL_ACE_INVALID")
        sid, rights, ace_type = ace["sid"], ace["rights"], ace["type"]
        if not isinstance(sid, str) or not isinstance(rights, str) or ace_type != "Allow":
            raise ValueError("ACL_ACE_INVALID")
        normalized.append((sid, rights))
    if len(normalized) != len(set(normalized)):
        raise ValueError("ACL_ACE_INVALID")
    required = {(SYSTEM_SID, "FullControl"), (ADMINISTRATORS_SID, "FullControl")}
    observer_right = "ReadAndExecute" if location == "release" else "Modify"
    allowed = required | {(observer_sid, observer_right)}
    if not required.issubset(set(normalized)) or set(normalized) != allowed:
        raise ValueError("ACL_ADMIN_SYSTEM_REQUIRED")
    return {"owner_sid": owner, "inheritance": inherited, "aces": sorted(normalized), "location": location}


def _task_is_s4u_for_principal(raw_xml: str, principal: str) -> bool:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return False
    actions = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "Actions"]
    principals = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "Principal"]
    if len(actions) != 1 or len(principals) != 1:
        return False
    context = actions[0].attrib.get("Context")
    principal_id = principals[0].attrib.get("id")
    if not isinstance(context, str) or not context or context != principal_id:
        return False
    values = {child.tag.rsplit("}", 1)[-1]: (child.text or "") for child in principals[0]}
    return values.get("UserId") == principal and values.get("LogonType") == "S4U"


def _same_path(left: str, right: Path) -> bool:
    return left.replace("\\", "/").rstrip("/").casefold() == str(right).replace("\\", "/").rstrip("/").casefold()


def _validate(observed: dict[str, Any], *, release_sha256: str, state_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    required = {"task_name", "task_xml", "task_action", "action_count", "principal", "principal_sid", "profile_path", "profile_acl", "release_acl", "state_path", "state_acl"}
    if set(observed) != required:
        raise ValueError("OBSERVATION_FIELDS_INVALID")
    if observed["task_name"] != TASK_NAME or not all(isinstance(observed[key], str) and observed[key] for key in {"task_xml", "task_action", "principal", "principal_sid", "profile_path"}):
        raise ValueError("TASK_OR_IDENTITY_INVALID")
    if observed["action_count"] != 1 or not _task_is_s4u_for_principal(observed["task_xml"], observed["principal"]):
        raise ValueError("TASK_NOT_S4U")
    principal_sid = observed["principal_sid"]
    if not SID_RE.fullmatch(principal_sid) or principal_sid in {SYSTEM_SID, ADMINISTRATORS_SID}:
        raise ValueError("OBSERVER_PRINCIPAL_PRIVILEGED")
    action = observed["task_action"].replace("\\", "/").casefold().strip()
    if not re.fullmatch(r"[a-z]:/[^\r\n]+/(?:terminal|terminal64)\.exe /portable", action):
        raise ValueError("TASK_ACTION_NOT_FIXED_PORTABLE")
    profile_acl = _acl(observed["profile_acl"], observer_sid=principal_sid, location="profile")
    release_acl = _acl(observed["release_acl"], observer_sid=principal_sid, location="release")
    state_acl = _acl(observed["state_acl"], observer_sid=principal_sid, location="state")
    if not isinstance(observed["state_path"], str) or not _same_path(observed["state_path"], state_root):
        raise ValueError("STATE_ROOT_MISMATCH")
    sources = {
        "task_xml_sha256": _sha(observed["task_xml"]), "task_action_sha256": _sha(observed["task_action"]),
        "profile_path_sha256": _sha(observed["profile_path"]), "profile_acl_sha256": _sha(_canonical(profile_acl)),
        "release_acl_sha256": _sha(_canonical(release_acl)), "state_path_sha256": _sha(observed["state_path"]),
        "state_acl_sha256": _sha(_canonical(state_acl)),
    }
    candidate = {"schema_version": SCHEMA, "release_a_payload_sha256": release_sha256, "task_name": TASK_NAME,
                 "principal": observed["principal"], "principal_sid": principal_sid, **sources, "broker_mutation": "NONE", "entry_eligible": False}
    candidate["candidate_sha256"] = _sha(_canonical(candidate))
    receipt = {"schema_version": RECEIPT_SCHEMA, "release_a_payload_sha256": release_sha256,
               "candidate_sha256": candidate["candidate_sha256"], "source_digests": sources,
               "writer_identity": "fixed-release-a-collector", "format_version": 1, "broker_mutation": "NONE", "entry_eligible": False}
    receipt["receipt_sha256"] = _sha(_canonical(receipt))
    return candidate, receipt


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(_canonical(value) + "\n"); handle.flush(); os.fsync(handle.fileno())
    temporary.replace(path)


def _observe_windows() -> dict[str, Any]:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_FIXED_OBSERVATION_REQUIRED")
    command = (
        "$ErrorActionPreference='Stop';$n='CS AI Lab MT5 Observer';$t=Get-ScheduledTask -TaskName $n;"
        "$a=@($t.Actions);if($a.Count -ne 1){throw 'one action required'};$x=Export-ScheduledTask -TaskName $n;"
        "$p=[string]$a[0].WorkingDirectory;$r='C:\\ProgramData\\ForexListener\\guardian-releases';$s='C:\\ProgramData\\ForexListener\\state\\m33-observer';"
        "function A($z){$q=Get-Acl $z;[pscustomobject]@{owner_sid=([Security.Principal.NTAccount]$q.Owner).Translate([Security.Principal.SecurityIdentifier]).Value;inheritance=$q.AreAccessRulesProtected;aces=@($q.Access|ForEach-Object{[pscustomobject]@{sid=$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value;rights=$_.FileSystemRights.ToString();type=$_.AccessControlType.ToString()}})}};"
        "[pscustomobject]@{task_name=$t.TaskName;task_xml=$x;task_action=([string]$a[0].Execute+' '+[string]$a[0].Arguments);action_count=$a.Count;principal=[string]$t.Principal.UserId;principal_sid=([Security.Principal.NTAccount]$t.Principal.UserId).Translate([Security.Principal.SecurityIdentifier]).Value;profile_path=$p;profile_acl=(A $p);release_acl=(A $r);state_path=$s;state_acl=(A $s)}|ConvertTo-Json -Compress -Depth 8"
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], text=True, capture_output=True, timeout=15, check=False)
    if result.returncode != 0:
        raise RuntimeError("WINDOWS_FIXED_OBSERVATION_FAILED")
    return _parse(result.stdout)


def _refusal_reason(error: BaseException) -> str:
    if isinstance(error, json.JSONDecodeError):
        return "OBSERVATION_JSON_INVALID"
    if isinstance(error, OSError):
        return "OBSERVATION_IO_FAILED"
    if isinstance(error, (ValueError, RuntimeError)) and str(error) in REFUSAL_REASONS:
        return str(error)
    return "OBSERVATION_INVALID"


def collect_once(root: Path, *, observe=_observe_windows, release_sha256: str | None = None) -> dict[str, Any]:
    release = release_sha256 or "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if not isinstance(release, str) or not SHA256_RE.fullmatch(release):
        raise ValueError("RELEASE_DIGEST_INVALID")
    root.mkdir(parents=True, exist_ok=True)
    try:
        candidate, receipt = _validate(observe(), release_sha256=release, state_root=root)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        refusal = {"schema_version": REFUSAL_SCHEMA, "release_a_payload_sha256": release,
                   "writer_identity": "fixed-release-a-collector", "format_version": 1,
                   "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                   "refusal_reason": _refusal_reason(exc), "broker_mutation": "NONE", "entry_eligible": False}
        refusal["receipt_sha256"] = _sha(_canonical(refusal)); _write_atomic(root / "trading_health_mt5_observer_bootstrap_refusal.local.json", refusal); raise
    run = root / "m33-observer-bootstrap" / candidate["candidate_sha256"][7:23]; run.mkdir(parents=True, exist_ok=True)
    _write_atomic(run / "candidate.json", candidate); _write_atomic(run / "receipt.json", receipt)
    pointer = {"schema_version": "forex.trading-health-mt5-observer-bootstrap-pointer.v1", "candidate_sha256": candidate["candidate_sha256"], "receipt_sha256": receipt["receipt_sha256"], "candidate_path": str((run / "candidate.json").relative_to(root)), "receipt_path": str((run / "receipt.json").relative_to(root))}
    _write_atomic(root / "trading_health_mt5_observer_bootstrap_current.local.json", pointer)
    return {"candidate_sha256": candidate["candidate_sha256"], "receipt_sha256": receipt["receipt_sha256"], "broker_mutation": "NONE", "entry_eligible": False}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect fixed no-order M33 observer candidate metadata.")
    parser.add_argument("--state-root", type=Path, required=True)
    args = parser.parse_args()
    print(_canonical(collect_once(args.state_root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
