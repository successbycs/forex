import importlib.util
import json
from pathlib import Path

SOURCE=Path("t480/trading_health_managed_mt5_inventory.py")
def module():
    spec=importlib.util.spec_from_file_location("managed_mt5_inventory",SOURCE); r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r); return r

def test_fixed_collector_writes_bound_identity_records_without_effect(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"
    (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    (tmp_path/"trading_health_mt5_expected_binding.local.json").write_text(json.dumps({"schema_version":"forex.trading-health-mt5-expected-binding.v1","task_name":"CS AI Lab MT5 Start","task_xml_sha256":m._sha("<Task><LogonType>S4U</LogonType></Task>"),"task_action_sha256":m._sha("C:/MT5/terminal64.exe /portable"),"principal":"SYSTEM","terminal_path":path,"terminal_config_sha256":m._sha(json.dumps({"terminal_path":path},sort_keys=True,separators=(",",":"))),"session_id":0,"parent_path":"C:/Windows/System32/taskeng.exe","command_line_sha256":m._sha("terminal64.exe /portable")}))
    def observe(expected):
        assert expected==path
        return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>S4U</LogonType></Task>","task_action":"C:/MT5/terminal64.exe /portable","principal":"SYSTEM","session_id":0,"configured_path":path,"processes":[{"pid":10,"path":path,"session_id":0,"command_line":"terminal64.exe /portable","parent_pid":1,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"one"},{"pid":11,"path":path,"session_id":0,"command_line":"terminal64.exe /portable","parent_pid":1,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"two"}]}
    result=m.collect_once(tmp_path,observe)
    assert result["broker_mutation"]=="NONE" and result["entry_eligible"] is False
    inventory=json.loads((tmp_path/"trading_health_mt5_inventory.local.json").read_text())
    assert [x["classification"] for x in inventory["processes"]]==["PRIMARY_MANAGED","ADDITIONAL_MANAGED"]

def test_collector_refuses_task_action_not_bound_to_configured_terminal(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"; (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    (tmp_path/"trading_health_mt5_expected_binding.local.json").write_text(json.dumps({"schema_version":"forex.trading-health-mt5-expected-binding.v1","task_name":"CS AI Lab MT5 Start","task_xml_sha256":m._sha("<Task><LogonType>S4U</LogonType></Task>"),"task_action_sha256":m._sha("C:/Other/terminal64.exe"),"principal":"SYSTEM","terminal_path":path,"terminal_config_sha256":m._sha(json.dumps({"terminal_path":path},sort_keys=True,separators=(",",":"))),"session_id":0}))
    def observe(_): return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>S4U</LogonType></Task>","task_action":"C:/Other/terminal64.exe","principal":"SYSTEM","session_id":0,"configured_path":"C:/MT5/terminal64.exe","processes":[]}
    import pytest
    with pytest.raises(ValueError,match="MISMATCH"): m.collect_once(tmp_path,observe)

def test_collector_refuses_non_s4u_task(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"; (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    (tmp_path/"trading_health_mt5_expected_binding.local.json").write_text(json.dumps({"schema_version":"forex.trading-health-mt5-expected-binding.v1","task_name":"CS AI Lab MT5 Start","task_xml_sha256":m._sha("<Task><LogonType>InteractiveToken</LogonType></Task>"),"task_action_sha256":m._sha("C:/MT5/terminal64.exe /portable"),"principal":"SYSTEM","terminal_path":path,"terminal_config_sha256":m._sha(json.dumps({"terminal_path":path},sort_keys=True,separators=(",",":"))),"session_id":0}))
    def observe(_): return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>InteractiveToken</LogonType></Task>","task_action":"C:/MT5/terminal64.exe","principal":"SYSTEM","session_id":0,"configured_path":"C:/MT5/terminal64.exe","processes":[]}
    import pytest
    with pytest.raises(ValueError,match="S4U"): m.collect_once(tmp_path,observe)

def test_collector_refuses_a_task_changed_from_the_immutable_expected_binding(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"; (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    (tmp_path/"trading_health_mt5_expected_binding.local.json").write_text(json.dumps({"schema_version":"forex.trading-health-mt5-expected-binding.v1","task_name":"CS AI Lab MT5 Start","task_xml_sha256":"sha256:"+"0"*64,"task_action_sha256":"sha256:"+"1"*64,"principal":"SYSTEM","terminal_path":path,"terminal_config_sha256":m._sha(json.dumps({"terminal_path":path},sort_keys=True,separators=(",",":"))),"session_id":0}))
    def observe(_): return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>S4U</LogonType></Task>","task_action":"C:/MT5/terminal64.exe /portable","principal":"SYSTEM","session_id":0,"configured_path":path,"processes":[]}
    import pytest
    with pytest.raises(ValueError,match="IMMUTABLE_EXPECTATION"): m.collect_once(tmp_path,observe)

def test_candidate_capture_is_read_only_and_cannot_provision_an_expected_binding(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"; (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    def observe(_): return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>S4U</LogonType></Task>","task_action":"C:/MT5/terminal64.exe /portable","principal":"SYSTEM","session_id":0,"configured_path":path,"processes":[{"pid":10,"path":path,"session_id":0,"command_line":"terminal64.exe /portable","parent_pid":1,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"one"}]}
    result=m.capture_candidate_once(tmp_path,observe)
    assert result["broker_mutation"]=="NONE" and result["entry_eligible"] is False
    assert not (tmp_path/"trading_health_mt5_expected_binding.local.json").exists()

def test_expected_command_hash_mismatch_fences_an_otherwise_matching_process(tmp_path):
    m=module(); path="C:/MT5/terminal64.exe"; (tmp_path/"m20_demo_listener_service.local.json").write_text(json.dumps({"terminal_path":path}))
    (tmp_path/"trading_health_mt5_expected_binding.local.json").write_text(json.dumps({"schema_version":"forex.trading-health-mt5-expected-binding.v1","task_name":"CS AI Lab MT5 Start","task_xml_sha256":m._sha("<Task><LogonType>S4U</LogonType></Task>"),"task_action_sha256":m._sha("C:/MT5/terminal64.exe /portable"),"principal":"SYSTEM","terminal_path":path,"terminal_config_sha256":m._sha(json.dumps({"terminal_path":path},sort_keys=True,separators=(",",":"))),"session_id":0,"parent_path":"C:/Windows/System32/taskeng.exe","command_line_sha256":"sha256:"+"0"*64}))
    def observe(_): return {"task_name":"CS AI Lab MT5 Start","task_xml":"<Task><LogonType>S4U</LogonType></Task>","task_action":"C:/MT5/terminal64.exe /portable","principal":"SYSTEM","configured_path":path,"processes":[{"pid":10,"path":path,"session_id":0,"command_line":"terminal64.exe /portable","parent_pid":1,"parent_path":"C:/Windows/System32/taskeng.exe","creation_id":"one"}]}
    m.collect_once(tmp_path,observe)
    inventory=json.loads((tmp_path/"trading_health_mt5_inventory.local.json").read_text())
    assert inventory["processes"][0]["classification"]=="UNATTRIBUTABLE"
