#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from forex.operating_schedule_register import OperatingRegisterError,load_register,report
def main(argv=None):
 p=argparse.ArgumentParser(description='Validate/report the declarative Forex operating register only.');p.add_argument('--register',type=Path,default=ROOT/'config/operating_schedule_register.json');a=p.parse_args(argv)
 try: print(json.dumps(report(load_register(a.register)),sort_keys=True,separators=(',',':')));return 0
 except OperatingRegisterError as exc: print(f'operating schedule register refused: {exc}',file=sys.stderr);return 2
if __name__=='__main__': raise SystemExit(main())
