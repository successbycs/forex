import json,subprocess,sys
from pathlib import Path
import pytest
from forex.operating_schedule_register import OperatingRegisterError,load_register,report
ROOT=Path(__file__).resolve().parents[1]
def test_register_validates_and_makes_no_runtime_claim():
 p=ROOT/'config/operating_schedule_register.json'; r=load_register(p);assert len(r['entries'])==8
 out=subprocess.run([sys.executable,'scripts/operating_schedule_register.py'],cwd=ROOT,text=True,capture_output=True);assert out.returncode==0;assert json.loads(out.stdout)['runtime_claim']=='NONE_DECLARATIVE_REGISTER_ONLY'
def test_register_refuses_duplicate_or_missing_fields(tmp_path):
 data=json.loads((ROOT/'config/operating_schedule_register.json').read_text());data['entries'].append(dict(data['entries'][0]));p=tmp_path/'bad.json';p.write_text(json.dumps(data))
 with pytest.raises(OperatingRegisterError):load_register(p)
def test_duplicate_json_and_direct_report_mapping_refuse(tmp_path):
 p=tmp_path/'dup.json';p.write_text('{"schema_version":"x","schema_version":"x","execution_authority":false,"entries":[]}')
 with pytest.raises(OperatingRegisterError,match='duplicate'):load_register(p)
 data=json.loads((ROOT/'config/operating_schedule_register.json').read_text());data['entries'][0]['inputs']='not-list'
 with pytest.raises(OperatingRegisterError):report(data)
 data=json.loads((ROOT/'config/operating_schedule_register.json').read_text());del data['entries'][0]['proof_surface'];p.write_text(json.dumps(data))
 with pytest.raises(OperatingRegisterError):load_register(p)
