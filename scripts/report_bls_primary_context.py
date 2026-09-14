#!/usr/bin/env python3
"""Report verified retained BLS evidence through primary context; no mutation."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from forex.bls_primary_context_integration import BLSPrimaryContextIntegrationError,report_bls_primary_context
from forex.primary_event_context import PrimaryEventContextError,load_contract
def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--store",type=Path,required=True);p.add_argument("--contract",type=Path,required=True);a=p.parse_args(argv)
 try:r=report_bls_primary_context(store_root=a.store,contract=load_contract(a.contract))
 except (PrimaryEventContextError,BLSPrimaryContextIntegrationError) as e:print(f"BLS primary context report refused: {e}",file=sys.stderr);return 2
 print(json.dumps(r,sort_keys=True,separators=(",",":"),allow_nan=False));return 0
if __name__=="__main__":raise SystemExit(main())
