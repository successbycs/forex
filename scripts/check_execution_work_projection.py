#!/usr/bin/env python3
"""Read-only consistency check for one execution-work JSON and Markdown pair."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src")); sys.path.insert(0,str(ROOT/"scripts"))
from check_execution_continuation import _read_plan
from forex.execution_work_projection import ProjectionError, validate
def main():
 p=argparse.ArgumentParser();p.add_argument("--work-plan",required=True);a=p.parse_args(); unresolved_path=ROOT/a.work_plan
 try:
  if unresolved_path.is_symlink(): raise ProjectionError("UNSAFE_WORK_PLAN")
  path=unresolved_path.resolve()
  if not path.is_relative_to((ROOT/"docs/plans").resolve()) or path.is_symlink(): raise ProjectionError("UNSAFE_WORK_PLAN")
  plan,raw=_read_plan(path); unresolved_md=ROOT/plan["markdown_plan"]
  if unresolved_md.is_symlink(): raise ProjectionError("UNSAFE_MARKDOWN_PLAN")
  md=unresolved_md.resolve()
  if not md.is_relative_to((ROOT/"docs/plans").resolve()) or md.is_symlink(): raise ProjectionError("UNSAFE_MARKDOWN_PLAN")
  print(json.dumps(validate(plan,md.read_text(),work_plan_bytes=raw),sort_keys=True));return 0
 except (OSError,KeyError,TypeError,ValueError,ProjectionError) as e: print(json.dumps({"status":"INVALID_WORK_PROJECTION","code":str(e)}));return 2
if __name__=="__main__": raise SystemExit(main())
