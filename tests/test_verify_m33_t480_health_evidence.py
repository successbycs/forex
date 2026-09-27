import importlib.util
import json
import shutil
from pathlib import Path

import pytest


SOURCE = Path("scripts/verify_m33_t480_health_evidence.py")
BUNDLE = Path("runs/local/m33-health-wave1/20260926T054000Z-postdeploy-coldboot")


def module():
    spec = importlib.util.spec_from_file_location("verify_m33_t480_health_evidence_test", SOURCE)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def copy_bundle(tmp_path):
    target = tmp_path / "bundle"
    shutil.copytree(BUNDLE, target)
    return target


def test_retained_coldboot_bundle_verifies(tmp_path, capsys):
    verifier = module()
    verifier.verify(copy_bundle(tmp_path))
    assert "FOREX_M33_LOCAL_TRADING_HEALTH_OK" in capsys.readouterr().out


def test_entry_capable_guardian_is_rejected(tmp_path):
    verifier = module()
    bundle = copy_bundle(tmp_path)
    path = bundle / "guardian-recurrence-cycle-2.json"
    value = json.loads(path.read_text())
    output = json.loads(value["result"]["stdout"])
    output["status"]["entry_eligible"] = True
    value["result"]["stdout"] = json.dumps(output)
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="fail-closed"):
        verifier.verify(bundle)


def test_missing_receipt_is_rejected(tmp_path):
    verifier = module()
    bundle = copy_bundle(tmp_path)
    (bundle / "final-held-readiness.json").unlink()
    with pytest.raises(ValueError, match="missing required"):
        verifier.verify(bundle)
