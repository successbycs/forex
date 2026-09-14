"""Strict read-only validation for the declared Forex operating register."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
SCHEMA="forex.operating-schedule-register.v1"
FIELDS={"id","owner","execution_authority","trigger","cadence","inputs","outputs","evidence_path","deployment_state","health_surface","proof_surface"}
class OperatingRegisterError(ValueError): pass
def _pairs(items):
 result={}
 for key,value in items:
  if key in result: raise OperatingRegisterError("duplicate JSON field")
  result[key]=value
 return result
def _validate(value):
 if not isinstance(value,dict) or set(value)!={"schema_version","execution_authority","entries"} or value.get("schema_version")!=SCHEMA or value.get("execution_authority") is not False or not isinstance(value.get("entries"),list): raise OperatingRegisterError("register schema is invalid")
 seen=set()
 for row in value["entries"]:
  if not isinstance(row,dict) or set(row)!=FIELDS or not isinstance(row.get("id"),str) or not row["id"] or row["id"] in seen or not isinstance(row.get("execution_authority"),bool) or not all(isinstance(row.get(k),str) and row[k] for k in FIELDS-{"id","execution_authority","inputs","outputs"}) or not isinstance(row.get("inputs"),list) or not isinstance(row.get("outputs"),list) or not all(isinstance(x,str) and x for x in row["inputs"]) or not all(isinstance(x,str) and x for x in row["outputs"]): raise OperatingRegisterError("register entry is invalid")
  seen.add(row["id"])
 if not seen: raise OperatingRegisterError("register has no entries")
 return value
def load_register(path:Path)->dict[str,Any]:
 if not isinstance(path,Path) or path.is_symlink() or not path.is_file(): raise OperatingRegisterError("register must be a regular file")
 try: value=json.loads(path.read_bytes(),object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(OperatingRegisterError("nonfinite JSON")))
 except (OSError,json.JSONDecodeError) as exc: raise OperatingRegisterError("register is not valid JSON") from exc
 return _validate(value)
def report(register:dict[str,Any])->dict[str,Any]:
 value=_validate(register)
 return {"schema_version":SCHEMA,"entry_count":len(value["entries"]),"entries":[{"id":x["id"],"deployment_state":x["deployment_state"],"execution_authority":x["execution_authority"],"health_surface":x["health_surface"],"proof_surface":x["proof_surface"]} for x in value["entries"]],"runtime_claim":"NONE_DECLARATIVE_REGISTER_ONLY","execution_authority":False}
