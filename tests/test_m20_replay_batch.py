import json
from pathlib import Path
import subprocess
import sys

import pytest

from forex.m20_replay_batch import ReplayBatchInputError, build_retained_replay_batch
from tests.test_m20_retained_export import operation_export


ROOT = Path(__file__).resolve().parents[1]


def _operation(root: Path, run: str, value: dict) -> Path:
    path = root / run / "demo-trading-operation.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_batch_reports_each_retained_source_without_aggregating_financial_results(tmp_path):
    first = _operation(tmp_path, "run-a", operation_export())
    _operation(tmp_path, "run-b", {"result": {"stdout": "not-json"}})
    before = first.read_bytes()
    report = build_retained_replay_batch(root=tmp_path)
    assert report["source_count"] == 2
    assert report["reported_source_count"] == 1
    assert report["refused_source_count"] == 1
    assert report["replayable_pair_count"] == 1
    assert report["broker_outcome_count"] == 0
    assert report["aggregate_financial_conclusion"] == "NOT_EVALUATED_SOURCE_LEVEL_DUPLICATES_AND_OUTCOMES_NOT_RECONCILED"
    assert report["sources"][1]["state"] == "REFUSED"
    assert report["sources"][1]["source_sha256"].startswith("sha256:")
    assert first.read_bytes() == before
    assert report["execution_authority"] is False


def test_batch_refuses_symlinked_direct_run(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    _operation(outside, "source", operation_export())
    (tmp_path / "linked-run").symlink_to(outside / "source", target_is_directory=True)
    with pytest.raises(ReplayBatchInputError, match="unsafe"):
        build_retained_replay_batch(root=tmp_path)


def test_batch_cli_outputs_read_only_inventory(tmp_path):
    _operation(tmp_path, "run-a", operation_export())
    process = subprocess.run([sys.executable, "scripts/m20_replay_batch_report.py", str(tmp_path)],
                             cwd=ROOT, text=True, capture_output=True, check=False)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)["reported_source_count"] == 1
