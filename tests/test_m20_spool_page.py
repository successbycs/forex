import base64, hashlib, json
from pathlib import Path

import pytest

from forex.m20_spool_page import SpoolPageError, retain_page_and_drain


def source(sequence):
    return {"schema_version":"forex.m20.latest-assessment.v1","listener_release_id":"a"*16,"assessment_sequence":sequence,
            "assessment_started_at_utc":"2026-09-12T00:00:00Z","assessment_completed_at_utc":"2026-09-12T00:00:01Z",
            "assessment":{"server":"GOMarketsMU-Demo","symbol":"EURUSD","decision_snapshot":{},"proposal":{}}}

def page(rows, after=0):
    encoded=[]
    for row in rows:
        raw=json.dumps(row,sort_keys=True,separators=(",", ":")).encode()
        encoded.append({"assessment_sequence":row["assessment_sequence"],"raw_sha256":"sha256:"+hashlib.sha256(raw).hexdigest(),"raw_base64":base64.b64encode(raw).decode()})
    stdout={"observation":"AVAILABLE","listener_release_id":"a"*16,"after_assessment_sequence":after,"records":encoded}
    return json.dumps({"operation":"m20_listener_spool_page","ok":True,"result":{"stdout":json.dumps(stdout)}}).encode()

def test_page_is_hash_bound_and_drains_before_cursor_advance(tmp_path):
    result=retain_page_and_drain(adapter_raw=page([source(1),source(2)]),capture_root=tmp_path)
    assert result["retained_count"]==2
    assert result["acknowledgement"]=="LOCAL_CURSOR_ADVANCED_AFTER_IMMUTABLE_RETENTION"
    assert (tmp_path/".m20-spool-drain-cursor.json").is_file()
    second=retain_page_and_drain(adapter_raw=page([source(3)],after=2),capture_root=tmp_path)
    assert second["retained_count"]==1


def test_first_page_can_use_a_later_source_baseline_but_following_pages_are_contiguous(tmp_path):
    result = retain_page_and_drain(adapter_raw=page([source(7)]), capture_root=tmp_path)
    assert result["retained_count"] == 1
    assert (tmp_path / ".m20-spool-drain-cursor.json").is_file()
    second = retain_page_and_drain(adapter_raw=page([source(8)], after=7), capture_root=tmp_path)
    assert second["retained_count"] == 1
    with pytest.raises(SpoolPageError, match="contiguous"):
        retain_page_and_drain(adapter_raw=page([source(10)], after=8), capture_root=tmp_path)

def test_page_refuses_hash_mismatch_or_gap(tmp_path):
    raw=page([source(1)])
    value=json.loads(raw); body=json.loads(value["result"]["stdout"]); body["records"][0]["raw_sha256"]="sha256:"+"0"*64;value["result"]["stdout"]=json.dumps(body)
    with pytest.raises(SpoolPageError,match="hash"):
        retain_page_and_drain(adapter_raw=json.dumps(value).encode(),capture_root=tmp_path)
    with pytest.raises(SpoolPageError,match="contiguous"):
        retain_page_and_drain(adapter_raw=page([source(1), source(3)]),capture_root=tmp_path)


def test_page_refuses_symlinked_mirror_parent_or_unfinished_staging(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".m20-spool-page-source").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SpoolPageError, match="mirror is unsafe"):
        retain_page_and_drain(adapter_raw=page([source(1)]), capture_root=tmp_path)
    assert not list(outside.iterdir())

    root = tmp_path / "safe"
    root.mkdir()
    mirror = root / ".m20-spool-page-source" / ("a" * 16)
    mirror.mkdir(parents=True)
    (mirror / ".00000000000000000001.pending").write_bytes(b"partial")
    with pytest.raises(SpoolPageError, match="unfinished staging"):
        retain_page_and_drain(adapter_raw=page([source(1)]), capture_root=root)
    assert not (mirror / "00000000000000000001.json").exists()
