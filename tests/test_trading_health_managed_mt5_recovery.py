import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest

SOURCE = Path("t480/trading_health_managed_mt5_recovery.py")
def module():
    spec=importlib.util.spec_from_file_location("managed_mt5", SOURCE); result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
def row(pid, creation, session=0, path="C:/MT5/terminal64.exe"):
    return {"pid":pid,"path":path,"session_id":session,"command_line_sha256":"sha256:"+"a"*64,"parent_pid":1,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":creation}
def binding(): return {"terminal_path":"C:/MT5/terminal64.exe","session_id":0,"parent_path":"C:/Windows/System32/taskeng.exe","command_line_sha256":"sha256:"+"a"*64}
def request(m, inv):
    now=datetime(2026,9,27,tzinfo=UTC); return {"schema_version":m.REQUEST_SCHEMA,"state":"PENDING","request_id":"a"*32,"generation":1,"recovery_epoch":1,"boot_id":"boot","configuration_fingerprint":"sha256:"+"b"*64,"account_scope_sha256":"sha256:"+"c"*64,"profile_sha256":"sha256:"+"d"*64,"task_binding_sha256":"sha256:"+"e"*64,"inventory_sha256":inv["inventory_sha256"],"action":"RECYCLE_MANAGED_SET_FLAT","issued_at_utc":now.isoformat(),"expires_at_utc":(now+timedelta(seconds=60)).isoformat(),"entry_eligible":False}
def test_inventory_and_duplicate_identity_are_fail_closed():
    m=module(); inv=m.classify_inventory([row(10,"one"),row(11,"two")],binding()); assert [x["classification"] for x in inv["processes"]]==["PRIMARY_MANAGED","ADDITIONAL_MANAGED"]
    assert [x["pid"] for x in m.verify_duplicate_targets(inv,inv)]==[11]
    changed=m.classify_inventory([row(10,"one"),row(11,"replacement")],binding())
    with pytest.raises(ValueError,match="IDENTITY_CHANGED"): m.verify_duplicate_targets(inv,changed)

def test_same_path_session_and_parent_with_a_different_command_is_unattributable():
    m=module(); expected=binding()|{"command_line_sha256":"sha256:"+"a"*64}
    different=row(10,"one"); different["command_line_sha256"]="sha256:"+"b"*64
    inv=m.classify_inventory([different],expected)
    assert inv["processes"][0]["classification"]=="UNATTRIBUTABLE"

def test_nonzero_observed_process_session_is_unattributable():
    m=module(); inv=m.classify_inventory([row(10,"one",session=1)],binding())
    assert inv["processes"][0]["classification"]=="UNATTRIBUTABLE"
def test_request_refuses_parallel_or_stale_recovery():
    m=module(); inv=m.classify_inventory([row(10,"one"),row(11,"two")],binding()); req=request(m,inv); now=datetime(2026,9,27,tzinfo=UTC)
    assert m.validate_request(req,None,now=now,binding_sha256="sha256:"+"e"*64,inventory_sha256=inv["inventory_sha256"],boot_id="boot",fingerprint="sha256:"+"b"*64) is None
    assert m.validate_request(req,{"schema_version":m.COORDINATOR_SCHEMA,"phase":"PENDING","boot_id":"boot","configuration_fingerprint":"sha256:"+"b"*64},now=now,binding_sha256="sha256:"+"e"*64,inventory_sha256=inv["inventory_sha256"],boot_id="boot",fingerprint="sha256:"+"b"*64).startswith("CROSS_PROTOCOL")

def test_new_schemas_accept_identity_contracts():
    from jsonschema import Draft202012Validator
    import json
    m=module(); inv=m.classify_inventory([row(10,"one")],binding())
    schema=json.loads(Path("config/schemas/trading-health-mt5-inventory.schema.json").read_text())
    assert not list(Draft202012Validator(schema).iter_errors(inv))
    authorization=json.loads(Path("config/schemas/trading-health-mt5-drill-authorization.schema.json").read_text())
    Draft202012Validator.check_schema(authorization)
    good={"schema_version":"forex.trading-health-mt5-drill-authorization.v1","scope":"M33_HELD_MT5_RECOVERY_DRILL","request_id":"a"*32,"boot_id":"boot","configuration_fingerprint":"sha256:"+"b"*64,"maintenance_hold":True,"entry_eligible":False,"order_authority":False}
    assert not list(Draft202012Validator(authorization).iter_errors(good))
    assert list(Draft202012Validator(authorization).iter_errors({**good,"order_authority":True}))
