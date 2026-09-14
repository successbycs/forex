#!/usr/bin/env python3
"""Read one fixed remote spool page, retain it locally, then drain it."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from forex.m20_spool_drain import _load_cursor
from forex.m20_spool_page import SpoolPageError, retain_page_and_drain


class SpoolPageExportError(ValueError):
 def __init__(self, code: str):
  super().__init__(code); self.code=code


def run_once(*, capture_root: Path) -> dict:
 try:
  cursor=_load_cursor(capture_root)
 except ValueError as exc:
  raise SpoolPageExportError("LOCAL_CURSOR_REFUSED") from exc
 after=0 if cursor is None else cursor["assessment_sequence"]
 try:
  out=subprocess.run([sys.executable,str(ROOT/"scripts"/"t480_adapter.py"),"execute","--operation","m20_listener_spool_page","--after-assessment-sequence",str(after)],capture_output=True,check=False,timeout=45)
 except subprocess.TimeoutExpired as exc:
  raise SpoolPageExportError("FIXED_OPERATION_TIMEOUT") from exc
 if out.returncode:
  raise SpoolPageExportError("FIXED_OPERATION_NONZERO")
 try:
  return retain_page_and_drain(adapter_raw=out.stdout,capture_root=capture_root)
 except (OSError, TypeError, ValueError) as exc:
  raise SpoolPageExportError("PAGE_OR_LOCAL_RETENTION_REFUSED") from exc

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--capture-root",type=Path,required=True);a=p.parse_args(argv)
 try:
  print(json.dumps(run_once(capture_root=a.capture_root),sort_keys=True,allow_nan=False));return 0
 except SpoolPageExportError as e:
  print(json.dumps({"schema_version":"forex.m20.spool-page-export-error.v1","state":"REFUSED","reason":e.code,"execution_authority":False},sort_keys=True),file=sys.stderr);return 2
if __name__=="__main__": raise SystemExit(main())
