import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

SOURCE = Path("t480/trading_health_managed_mt5_recovery_executor.py")

def module():
    spec=importlib.util.spec_from_file_location("managed_mt5_executor", SOURCE); result=importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result

def write(path, value): path.write_text(json.dumps(value), encoding="utf-8")

def test_executor_refuses_to_dispatch_effect_off_windows(tmp_path):
    m=module(); now=datetime(2026,9,27,tzinfo=UTC); fingerprint="sha256:"+"a"*64; binding="sha256:"+"b"*64; inventory="sha256:"+"c"*64
    request={"schema_version":"forex.trading-health-mt5-recovery-request.v1","state":"PENDING","request_id":"d"*32,"generation":1,"recovery_epoch":1,"boot_id":"boot","configuration_fingerprint":fingerprint,"account_scope_sha256":"sha256:"+"e"*64,"profile_sha256":"sha256:"+"f"*64,"task_binding_sha256":binding,"inventory_sha256":inventory,"action":"RECYCLE_MANAGED_SET_FLAT","issued_at_utc":now.isoformat(),"expires_at_utc":(now+timedelta(seconds=60)).isoformat(),"entry_eligible":False}
    write(tmp_path/"trading_health_mt5_recovery_request.local.json",request)
    write(tmp_path/"trading_health_mt5_recovery_ledger.local.json",{"schema_version":"forex.trading-health-mt5-recovery-ledger.v1","boot_id":"boot","last_generation":1,"last_recovery_epoch":1,"active_request_id":"d"*32,"phase":"PENDING"})
    write(tmp_path/"trading_health_mt5_recovery_coordinator.local.json",{"schema_version":"forex.trading-health-recovery-coordinator.v1","recovery_epoch":1,"protocol":"MT5_V1","request_id":"d"*32,"generation":1,"boot_id":"boot","configuration_fingerprint":fingerprint,"phase":"PENDING"})
    write(tmp_path/"trading_health_mt5_task_binding.local.json",{"binding_sha256":binding})
    write(tmp_path/"trading_health_mt5_inventory.local.json",{"inventory_sha256":inventory})
    write(tmp_path/"trading_health_intent.local.json",{"mode":"RUN_DEMO"}); write(tmp_path/"m20_demo_maintenance_hold.local.json",{"enabled":True}); write(tmp_path/"trading_health_mt5_drill_authorization.local.json",{"schema_version":"forex.trading-health-mt5-drill-authorization.v1","scope":"M33_HELD_MT5_RECOVERY_DRILL","request_id":"d"*32,"boot_id":"boot","configuration_fingerprint":fingerprint,"maintenance_hold":True,"entry_eligible":False,"order_authority":False})
    receipt=m.execute_once(tmp_path,now)
    assert receipt["state"]=="INTERVENTION_REQUIRED" and receipt["reason"] in {"WINDOWS_FIXED_EFFECT_REQUIRED", "FRESH_DUPLICATE_IDENTITY_OR_INVENTORY_INVALID"}
    assert receipt["broker_mutation"]=="NONE" and receipt["entry_eligible"] is False
    assert json.loads((tmp_path/"trading_health_mt5_recovery_ledger.local.json").read_text())["phase"]=="INTERVENTION_REQUIRED"

def test_executor_refuses_missing_or_bad_inputs_without_effect(tmp_path):
    m=module(); receipt=m.execute_once(tmp_path,datetime(2026,9,27,tzinfo=UTC))
    assert receipt["state"]=="REFUSED" and receipt["broker_mutation"]=="NONE" and receipt["entry_eligible"] is False

def test_executor_fences_an_active_listener_recovery_protocol(tmp_path):
    m=module(); now=datetime(2026,9,27,tzinfo=UTC); fingerprint="sha256:"+"a"*64; binding="sha256:"+"b"*64; inventory="sha256:"+"c"*64
    request={"schema_version":"forex.trading-health-mt5-recovery-request.v1","state":"PENDING","request_id":"d"*32,"generation":1,"recovery_epoch":1,"boot_id":"boot","configuration_fingerprint":fingerprint,"account_scope_sha256":"sha256:"+"e"*64,"profile_sha256":"sha256:"+"f"*64,"task_binding_sha256":binding,"inventory_sha256":inventory,"action":"RECYCLE_MANAGED_SET_FLAT","issued_at_utc":now.isoformat(),"expires_at_utc":(now+timedelta(seconds=60)).isoformat(),"entry_eligible":False}
    write(tmp_path/"trading_health_mt5_recovery_request.local.json",request); write(tmp_path/"trading_health_mt5_recovery_ledger.local.json",{"schema_version":"forex.trading-health-mt5-recovery-ledger.v1","boot_id":"boot","last_generation":1,"last_recovery_epoch":1,"active_request_id":"d"*32,"phase":"PENDING"}); write(tmp_path/"trading_health_mt5_recovery_coordinator.local.json",{"schema_version":"forex.trading-health-recovery-coordinator.v1","recovery_epoch":1,"protocol":"MT5_V1","request_id":"d"*32,"generation":1,"boot_id":"boot","configuration_fingerprint":fingerprint,"phase":"PENDING"}); write(tmp_path/"trading_health_mt5_task_binding.local.json",{"binding_sha256":binding}); write(tmp_path/"trading_health_mt5_inventory.local.json",{"inventory_sha256":inventory}); write(tmp_path/"trading_health_intent.local.json",{"mode":"RUN_DEMO"}); write(tmp_path/"m20_demo_maintenance_hold.local.json",{"enabled":True})
    write(tmp_path/"trading_health_recovery_ledger.local.json",{"schema_version":"forex.trading-health-recovery-ledger.v1","boot_id":"boot","last_generation":1,"attempts_utc":[],"active_request_id":"9"*32,"phase":"PENDING"}); write(tmp_path/"trading_health_recovery_request.local.json",{"schema_version":"forex.trading-health-recovery-request.v2","request_id":"9"*32})
    receipt=m.execute_once(tmp_path,now)
    assert receipt["state"]=="REFUSED" and receipt["reason"]=="CROSS_PROTOCOL_LISTENER_RECOVERY_ACTIVE_OR_INVALID"

def test_executor_refuses_each_tampered_coordinator_identity_field(tmp_path):
    m=module(); now=datetime(2026,9,27,tzinfo=UTC); f="sha256:"+"a"*64; b="sha256:"+"b"*64; i="sha256:"+"c"*64
    request={"schema_version":"forex.trading-health-mt5-recovery-request.v1","state":"PENDING","request_id":"d"*32,"generation":1,"recovery_epoch":1,"boot_id":"boot","configuration_fingerprint":f,"account_scope_sha256":"sha256:"+"e"*64,"profile_sha256":"sha256:"+"f"*64,"task_binding_sha256":b,"inventory_sha256":i,"action":"RECYCLE_MANAGED_SET_FLAT","issued_at_utc":now.isoformat(),"expires_at_utc":(now+timedelta(seconds=60)).isoformat(),"entry_eligible":False}
    write(tmp_path/"trading_health_mt5_recovery_request.local.json",request); write(tmp_path/"trading_health_mt5_recovery_ledger.local.json",{"schema_version":"forex.trading-health-mt5-recovery-ledger.v1","boot_id":"boot","last_generation":1,"last_recovery_epoch":1,"active_request_id":"d"*32,"phase":"PENDING"}); write(tmp_path/"trading_health_mt5_task_binding.local.json",{"binding_sha256":b}); write(tmp_path/"trading_health_mt5_inventory.local.json",{"inventory_sha256":i}); write(tmp_path/"trading_health_intent.local.json",{"mode":"RUN_DEMO"}); write(tmp_path/"m20_demo_maintenance_hold.local.json",{"enabled":True}); write(tmp_path/"trading_health_mt5_drill_authorization.local.json",{"schema_version":"forex.trading-health-mt5-drill-authorization.v1","scope":"M33_HELD_MT5_RECOVERY_DRILL","request_id":"d"*32,"boot_id":"boot","configuration_fingerprint":f,"maintenance_hold":True,"entry_eligible":False,"order_authority":False})
    base={"schema_version":"forex.trading-health-recovery-coordinator.v1","recovery_epoch":1,"protocol":"MT5_V1","request_id":"d"*32,"generation":1,"boot_id":"boot","configuration_fingerprint":f,"phase":"PENDING"}
    for field,wrong in (("generation",2),("recovery_epoch",2),("boot_id","other"),("configuration_fingerprint","sha256:"+"0"*64)):
        write(tmp_path/"trading_health_mt5_recovery_coordinator.local.json",base|{field:wrong})
        assert m.execute_once(tmp_path,now)["reason"]=="MT5_RECOVERY_OWNERSHIP_INVALID"

def test_reconcile_refuses_minimal_or_undispatched_records_instead_of_false_verification(tmp_path):
    m=module(); now=datetime(2026,9,27,tzinfo=UTC); request={"request_id":"d"*32,"generation":1,"recovery_epoch":1,"boot_id":"boot","configuration_fingerprint":"sha256:"+"a"*64}
    write(tmp_path/"trading_health_mt5_recovery_request.local.json",request)
    write(tmp_path/"trading_health_mt5_recovery_ledger.local.json",{"phase":"CLAIMED","active_request_id":"d"*32})
    write(tmp_path/"trading_health_mt5_recovery_coordinator.local.json",{"phase":"CLAIMED","request_id":"d"*32})
    write(tmp_path/"trading_health_mt5_inventory.local.json",{"processes":[{"classification":"PRIMARY_MANAGED"}]})
    write(tmp_path/"m20_demo_listener_status.local.json",{"state":"MAINTENANCE_HOLD"}); write(tmp_path/"trading_health_status.local.json",{"entry_eligible":False}); write(tmp_path/"m20_demo_maintenance_hold.local.json",{"enabled":True})
    receipt=m.reconcile_once(tmp_path,now)
    assert receipt["state"]=="INTERVENTION_REQUIRED" and receipt["reason"] in {"RECONCILIATION_RECORD_UNREADABLE","RECONCILIATION_REQUEST_OR_BINDING_INVALID"}
    assert receipt["broker_mutation"]=="NONE" and receipt["entry_eligible"] is False

def test_fixed_held_account_witness_is_collected_from_the_bound_listener_release(tmp_path, monkeypatch):
    m=module(); now=datetime(2026,9,27,tzinfo=UTC); fingerprint="sha256:"+"a"*64
    request={"boot_id":"boot","configuration_fingerprint":fingerprint,"account_scope_sha256":"sha256:"+"b"*64,"profile_sha256":"sha256:"+"c"*64}
    write(tmp_path/"trading_health_runtime_binding.local.json",{"listener_release_id":"d"*16,"boot_id":"boot","configuration_fingerprint":fingerprint,"account_scope_sha256":request["account_scope_sha256"],"profile_sha256":request["profile_sha256"]})
    write(tmp_path/"m20_demo_listener_service.local.json",{"python_path":"python","FOREX_M20_CONFIGURATION_FINGERPRINT":fingerprint})
    payload={"maintenance_hold":True,"listener_release_id":"d"*16,"assessment":{"marker":"FOREX_M20_DEMO_HELD_READINESS_ASSESSMENT_OK","server":"GOMarketsMU-Demo","currency":"AUD","symbol":"EURUSD","open_positions":0,"pending_orders":0,"broker_mutation":"NONE","order_submission":"STRUCTURALLY_UNAVAILABLE"}}
    monkeypatch.setattr(m.subprocess,"run",lambda *_a,**_k:type("R",(),{"returncode":0,"stdout":json.dumps(payload)})())
    witness=m._collect_held_account_witness(tmp_path,request,now)
    assert witness["broker_mutation"]=="NONE" and witness["entry_eligible"] is False
    assert json.loads((tmp_path/"trading_health_mt5_held_account_witness.local.json").read_text())["server"]=="GOMarketsMU-Demo"
