#!/usr/bin/env python3
"""Verify local retained BLS monthly evidence; never fetch or mutate it."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from forex.bls_primary_source_verifier import BLSPrimarySourceVerificationError, verify_bls_primary_source

def main(argv: list[str] | None = None) -> int:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--store",type=Path,required=True)
 args=parser.parse_args(argv)
 try:result=verify_bls_primary_source(args.store)
 except BLSPrimarySourceVerificationError as exc:
  print(f"BLS primary-source verification refused: {exc}",file=sys.stderr);return 2
 print(json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False));return 0
if __name__=="__main__":raise SystemExit(main())
