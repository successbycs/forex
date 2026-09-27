import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path("t480/trading_health_mt5_observer_collector.py")

def module():
    spec = importlib.util.spec_from_file_location("observer_collector", SOURCE)
    value = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(value); return value

def observation():
    acl = lambda: {"owner_sid":"S-1-5-32-544","inheritance":False,"aces":[{"sid":"S-1-5-18","rights":"FullControl","type":"Allow"},{"sid":"S-1-5-32-544","rights":"FullControl","type":"Allow"},{"sid":"S-1-5-21-9","rights":"Modify","type":"Allow"}]}
    release = acl(); release["aces"][-1]["rights"]="ReadAndExecute"
    return {"task_name":"CS AI Lab MT5 Observer","task_xml":"<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal></Principals><Actions Context=\"observer\"><Exec/></Actions></Task>","task_action":"C:/Observer/terminal64.exe /portable","action_count":1,"principal":"T480\\ForexMt5Observer","principal_sid":"S-1-5-21-9","profile_path":"C:/Observer","profile_acl":acl(),"release_acl":release,"state_path":"","state_acl":acl()}

def observed_for(root):
    raw=observation(); raw["state_path"]=str(root); return raw

def test_fixed_candidate_collector_writes_no_effect_chain(tmp_path):
    m=module(); result=m.collect_once(tmp_path, observe=lambda:observed_for(tmp_path), release_sha256="sha256:"+"a"*64)
    assert result["broker_mutation"] == "NONE" and result["entry_eligible"] is False
    pointer=json.loads((tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").read_text())
    candidate=json.loads((tmp_path/pointer["candidate_path"]).read_text())
    receipt=json.loads((tmp_path/pointer["receipt_path"]).read_text())
    assert candidate["candidate_sha256"] == receipt["candidate_sha256"]
    source=SOURCE.read_text()
    assert "OrderSend(" not in source and "Start-ScheduledTask" not in source and "Stop-Process" not in source

@pytest.mark.parametrize("field,value,reason",[("task_action","C:/Observer/terminal64.exe /portable --password x","TASK_ACTION_NOT_FIXED_PORTABLE"),("principal_sid","S-1-5-18","OBSERVER_PRINCIPAL_PRIVILEGED")])
def test_candidate_collector_refuses_unsafe_identity(tmp_path,field,value,reason):
    m=module(); raw=observed_for(tmp_path); raw[field]=value
    with pytest.raises(ValueError, match=reason): m.collect_once(tmp_path, observe=lambda:raw)

def test_candidate_collector_rejects_observer_release_write_and_preserves_prior_output(tmp_path):
    m=module(); m.collect_once(tmp_path, observe=lambda:observed_for(tmp_path)); before=(tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").read_bytes()
    raw=observed_for(tmp_path); raw["release_acl"]["aces"].append({"sid":"S-1-5-21-9","rights":"Modify","type":"Allow"})
    with pytest.raises(ValueError, match="ACL_ADMIN_SYSTEM_REQUIRED"): m.collect_once(tmp_path, observe=lambda:raw)
    assert (tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").read_bytes()==before

def test_failure_writes_nonsecret_refusal_without_current_pointer(tmp_path):
    m=module(); raw=observed_for(tmp_path); raw["action_count"]=2
    with pytest.raises(ValueError, match="TASK_NOT_S4U"): m.collect_once(tmp_path, observe=lambda:raw)
    refusal=json.loads((tmp_path/"trading_health_mt5_observer_bootstrap_refusal.local.json").read_text())
    assert refusal["broker_mutation"]=="NONE" and refusal["entry_eligible"] is False
    assert not (tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").exists()

def test_candidate_collector_rejects_unknown_acl_and_wrong_state_root(tmp_path):
    m=module(); raw=observed_for(tmp_path)
    raw["state_acl"]["aces"].append({"sid":"S-1-1-0","rights":"Modify","type":"Allow"})
    with pytest.raises(ValueError, match="ACL_ADMIN_SYSTEM_REQUIRED"): m.collect_once(tmp_path, observe=lambda:raw)
    raw=observed_for(tmp_path); raw["state_path"]=str(tmp_path/"other")
    with pytest.raises(ValueError, match="STATE_ROOT_MISMATCH"): m.collect_once(tmp_path, observe=lambda:raw)

@pytest.mark.parametrize("xml",[
    "<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal><Principal id=\"decoy\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal></Principals><Actions Context=\"observer\"><Exec/></Actions></Task>",
    "<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal></Principals><Actions Context=\"decoy\"><Exec/></Actions></Task>",
    "<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>InteractiveToken</LogonType></Principal></Principals><Actions Context=\"observer\"><Exec/></Actions></Task>",
    "<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal></Principals><Actions><Exec/></Actions></Task>",
    "<Task><Principals><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal><Principal id=\"observer\"><UserId>T480\\ForexMt5Observer</UserId><LogonType>S4U</LogonType></Principal></Principals><Actions Context=\"observer\"><Exec/></Actions></Task>",
])
def test_candidate_collector_rejects_decoy_or_unbound_task_principal(tmp_path,xml):
    m=module(); raw=observed_for(tmp_path); raw["task_xml"]=xml
    with pytest.raises(ValueError,match="TASK_NOT_S4U"): m.collect_once(tmp_path,observe=lambda:raw)

def test_candidate_collector_rejects_duplicate_acl_ace(tmp_path):
    m=module(); raw=observed_for(tmp_path)
    raw["profile_acl"]["aces"].append(dict(raw["profile_acl"]["aces"][0]))
    with pytest.raises(ValueError,match="ACL_ACE_INVALID"): m.collect_once(tmp_path,observe=lambda:raw)

def test_refusal_is_allowlisted_and_does_not_retain_raw_observation(tmp_path):
    m=module(); raw=observed_for(tmp_path); raw["task_action"]="C:/Observer/terminal64.exe /portable --password secret-value"
    with pytest.raises(ValueError): m.collect_once(tmp_path, observe=lambda:raw)
    refusal=json.loads((tmp_path/"trading_health_mt5_observer_bootstrap_refusal.local.json").read_text())
    assert refusal["schema_version"]=="forex.trading-health-mt5-observer-bootstrap-refusal.v1"
    assert refusal["refusal_reason"]=="TASK_ACTION_NOT_FIXED_PORTABLE"
    assert "secret-value" not in json.dumps(refusal)

@pytest.mark.parametrize("failure_call",[2,3])
def test_publication_failure_retains_previous_pointer(tmp_path,monkeypatch,failure_call):
    m=module(); m.collect_once(tmp_path, observe=lambda:observed_for(tmp_path), release_sha256="sha256:"+"a"*64)
    before=(tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").read_bytes()
    raw=observed_for(tmp_path); raw["profile_path"]="C:/DifferentObserver"
    original=m._write_atomic; calls=[]
    def failing(path,value):
        calls.append(path)
        if len(calls)==failure_call: raise OSError("injected")
        original(path,value)
    monkeypatch.setattr(m,"_write_atomic",failing)
    with pytest.raises(OSError): m.collect_once(tmp_path, observe=lambda:raw, release_sha256="sha256:"+"b"*64)
    assert (tmp_path/"trading_health_mt5_observer_bootstrap_current.local.json").read_bytes()==before

def test_release_digest_must_be_exact_sha256(tmp_path):
    m=module()
    with pytest.raises(ValueError,match="RELEASE_DIGEST_INVALID"):
        m.collect_once(tmp_path, observe=lambda:observed_for(tmp_path), release_sha256="sha256:short")

def test_parser_rejects_duplicate_and_nonfinite_json():
    m=module()
    with pytest.raises(ValueError, match="DUPLICATE_JSON_FIELD"): m._parse('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="NONFINITE_JSON"): m._parse('{"a":NaN}')
