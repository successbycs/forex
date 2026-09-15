from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gdelt_secret_provisioner", ROOT / "scripts" / "provision_gdelt_egress_secrets.py")
assert SPEC and SPEC.loader
provisioner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provisioner)


def test_provision_creates_matching_owner_only_ignored_local_files_and_is_idempotent(tmp_path: Path):
    provisioner.provision(tmp_path)
    values = {}
    for key, name in (("FOREX_GDELT_EGRESS_BEARER", provisioner.BEARER_NAME), ("FOREX_GDELT_CANDIDATE_SIGNING_KEY", provisioner.SIGNING_NAME)):
        path = tmp_path / name
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        values[key] = path.read_text().strip()
        assert len(values[key]) >= 32
    assert values["FOREX_GDELT_EGRESS_BEARER"] != values["FOREX_GDELT_CANDIDATE_SIGNING_KEY"]
    assert (tmp_path / provisioner.ENV_NAME).read_text().splitlines() == [f"{key}={values[key]}" for key in provisioner.REQUIRED]
    provisioner.provision(tmp_path)


def test_provision_refuses_partial_existing_set(tmp_path: Path):
    (tmp_path / provisioner.BEARER_NAME).write_text("x")
    with pytest.raises(RuntimeError, match="partial"):
        provisioner.provision(tmp_path)
