#!/usr/bin/env python3
"""Report non-active FOMC/ECB timing-source amendment evidence; read only."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from forex.policy_timing_amendment import PolicyTimingAmendmentError,load_draft,report_amendment
from forex.primary_event_context import PrimaryEventContextError,load_contract
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--baseline",type=Path,required=True);p.add_argument("--draft",type=Path,required=True);p.add_argument("--store",type=Path,required=True);a=p.parse_args(argv)
 try:r=report_amendment(baseline_contract=load_contract(a.baseline),draft=load_draft(a.draft),store_root=a.store)
 except (PrimaryEventContextError,PolicyTimingAmendmentError) as e:print(f"policy timing amendment report refused: {e}",file=sys.stderr);return 2
 print(json.dumps(r,sort_keys=True,separators=(",",":"),allow_nan=False));return 0
if __name__=="__main__":raise SystemExit(main())
