#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 runs/evidence/M31/<timestamp> FROM_UTC TO_UTC" >&2
  echo "UTC bounds must be pre-declared whole-second instants with Z suffix; interval is at most 24 hours." >&2
  exit 2
fi

bundle=$1
from_utc=$2
to_utc=$3
if [[ -e "$bundle" ]]; then
  echo "M31 capture refuses to overwrite an existing bundle" >&2
  exit 2
fi
if [[ -n $(git status --porcelain) ]]; then
  echo "M31 capture requires a clean, committed checkout so its revision can be proved" >&2
  exit 2
fi
mkdir -p "$(dirname "$bundle")"
mkdir "$bundle"
trap 'echo "M31 capture stopped; preserve partial bundle for investigation" >&2' ERR

python3 - "$bundle/protocol.json" "$from_utc" "$to_utc" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

path, start, end = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def utc(value):
    if not value.endswith("Z"):
        raise SystemExit("M31 capture refused: UTC instant requires Z suffix")
    try: parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError: raise SystemExit("M31 capture refused: invalid UTC instant")
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise SystemExit("M31 capture refused: UTC instant must be whole-second")
    return parsed
if not utc(start) < utc(end) or (utc(end) - utc(start)).total_seconds() > 86400:
    raise SystemExit("M31 capture refused: interval must be positive and at most 24 hours")
protocol = {"schema_version":"forex.m31.evaluation-protocol.v1","interval":{"from_utc":start,"to_utc":end,"bounds":"inclusive/exclusive"},"baseline":{"kind":"NO_CHANGE","trade_count":0,"realized_pnl_aud":0,"cost_aud":0},"server":"GOMarketsMU-Demo","symbol":"EURUSD","captured_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
path.write_text(json.dumps(protocol, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY

python3 scripts/postgres_pgvector_adapter.py forex-m1-postgres-completeness-summary --from-utc "$from_utc" --to-utc "$to_utc" >"$bundle/completeness.json"
python3 scripts/postgres_pgvector_adapter.py forex-m20-lifecycle-summary >"$bundle/lifecycle.json"
python3 scripts/t480_adapter.py execute --operation m20_all_demo_history_export >"$bundle/broker-history.json"
python3 scripts/m31_scorecard.py --protocol "$bundle/protocol.json" --completeness "$bundle/completeness.json" --lifecycle "$bundle/lifecycle.json" --format json >"$bundle/scorecard.json"
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

bundle = Path(sys.argv[1])
names = ("protocol.json", "completeness.json", "lifecycle.json", "broker-history.json", "scorecard.json", "revision.txt")
manifest = {"schema_version":"forex.m31.evidence-bundle.v1","milestone_id":"M31","captured_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"git_revision":(bundle / "revision.txt").read_text().strip(),"observed_result":"FOREX_M31_EVIDENCE_CAPTURED","execution_authority":False,"artifacts":[{"path":name,"sha256":"sha256:" + hashlib.sha256((bundle / name).read_bytes()).hexdigest()} for name in names]}
(bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
bash scripts/verify_m31_evidence.sh "$bundle"
