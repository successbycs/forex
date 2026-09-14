#!/usr/bin/env python3
"""Validate/report the non-active BLS URL-template amendment draft."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from forex.bls_url_template_amendment import BLSURLTemplateAmendmentError,load_draft,report_amendment
from forex.bls_primary_source_verifier import BLSPrimarySourceVerificationError,verify_bls_primary_source
from forex.primary_event_context import PrimaryEventContextError,load_contract
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--baseline",type=Path,required=True);parser.add_argument("--draft",type=Path,required=True)
 source=parser.add_mutually_exclusive_group();source.add_argument("--candidates",type=Path);source.add_argument("--store",type=Path,help="explicit existing BLS retained-source root; read only")
 args=parser.parse_args(argv)
 try:
  candidates=(verify_bls_primary_source(args.store)["context_candidates"] if args.store is not None
              else [] if args.candidates is None else json.loads(args.candidates.read_bytes()))
  report=report_amendment(baseline_contract=load_contract(args.baseline),draft=load_draft(args.draft),candidates=candidates)
 except (OSError,json.JSONDecodeError,PrimaryEventContextError,BLSURLTemplateAmendmentError,BLSPrimarySourceVerificationError) as exc:
  print(f"BLS URL-template amendment report refused: {exc}",file=sys.stderr);return 2
 print(json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False));return 0
if __name__=="__main__":raise SystemExit(main())
