"""Immutable local retention for one fixed all-Demo-history adapter response."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from forex.m20_history_report import HistoryReportInputError, build_history_report


SCHEMA_VERSION = "forex.m20.all-history-capture.v1"


class HistoryCaptureError(ValueError):
    """A fixed history response cannot safely be retained."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise HistoryCaptureError("history receipt is not finite JSON") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _trusted(root: Path) -> Path:
    from forex.event_capture_store import _no_symlink_ancestors
    if not isinstance(root, Path) or not root.exists() or root.is_symlink() or not root.is_dir():
        raise HistoryCaptureError("history capture root must be an existing trusted directory")
    try:
        _no_symlink_ancestors(root)
    except ValueError as exc:
        raise HistoryCaptureError("history capture root has unsafe symlink ancestry") from exc
    return root


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def retain_history_response(*, root: Path, adapter_response_raw: bytes) -> tuple[Path, str, dict[str, Any]]:
    """Retain one valid fixed response and its report, never replacing bytes."""
    root = _trusted(root)
    try:
        report = build_history_report(adapter_response_raw)
    except HistoryReportInputError as exc:
        raise HistoryCaptureError(f"fixed history response refused: {exc}") from exc
    response_sha256 = _sha(adapter_response_raw)
    report_raw = _canonical(report)
    report_sha256 = _sha(report_raw)
    target = root / f"m20-all-history-{response_sha256[7:23]}"
    receipt_content = {
        "schema_version": SCHEMA_VERSION,
        "operation": "m20_all_demo_history_export",
        "adapter_response_sha256": response_sha256,
        "history_report_sha256": report_sha256,
        "captured_at_utc": report["captured_at_utc"],
        "server": report["server"],
        "currency": report["currency"],
        "execution_authority": False,
    }
    receipt_raw = _canonical({**receipt_content, "receipt_sha256": _sha(_canonical(receipt_content))})
    expected = {"adapter-response.json": adapter_response_raw, "history-report.json": report_raw, "receipt.json": receipt_raw}
    try:
        target.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        created = False
    if not created:
        if target.is_symlink() or not target.is_dir() or {item.name for item in target.iterdir()} != set(expected):
            raise HistoryCaptureError("existing history capture is incomplete or unsafe")
        if any((target / name).is_symlink() or (target / name).read_bytes() != raw for name, raw in expected.items()):
            raise HistoryCaptureError("existing history capture conflicts")
        return target, "EXISTING", report
    try:
        _write_new(target / "adapter-response.json", adapter_response_raw)
        _write_new(target / "history-report.json", report_raw)
        _write_new(target / "receipt.json", receipt_raw)
        directory = os.open(target, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        # Preserve a partial directory for investigation; never overwrite it.
        raise
    return target, "CREATED", report
