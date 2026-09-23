#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 runs/evidence/M31/<timestamp> runs/protocols/M31/<timestamp>" >&2
  exit 2
fi

bundle=$1
protocol_directory=$2
if [[ -e "$bundle" ]]; then
  echo "M31 capture refuses to overwrite an existing bundle" >&2
  exit 2
fi
if [[ -n $(git status --porcelain) ]]; then
  echo "M31 capture requires a clean, committed checkout so its revision can be proved" >&2
  exit 2
fi
if [[ ! -f "$protocol_directory/protocol.json" || ! -f "$protocol_directory/receipt.json" ]]; then
  echo "M31 capture requires an immutable declared protocol and receipt" >&2
  exit 2
fi
mkdir -p "$(dirname "$bundle")"
mkdir "$bundle"
trap 'echo "M31 capture stopped; preserve partial bundle for investigation" >&2' ERR

python3 - "$protocol_directory" "$bundle/protocol.json" <<'PY'
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

source, path = Path(sys.argv[1]), Path(sys.argv[2])
def utc(value):
    if not value.endswith("Z"):
        raise SystemExit("M31 capture refused: UTC instant requires Z suffix")
    try: parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError: raise SystemExit("M31 capture refused: invalid UTC instant")
    if parsed.tzinfo != timezone.utc or parsed.microsecond:
        raise SystemExit("M31 capture refused: UTC instant must be whole-second")
    return parsed
raw = (source / "protocol.json").read_bytes(); protocol = json.loads(raw); receipt = json.loads((source / "receipt.json").read_text())
required = {"schema_version","interval","baseline","server","symbol","captured_at_utc"}
if set(protocol) != required or protocol.get("schema_version") != "forex.m31.evaluation-protocol.v1" or protocol.get("server") != "GOMarketsMU-Demo" or protocol.get("symbol") != "EURUSD": raise SystemExit("M31 capture refused: protocol identity is invalid")
if receipt.get("schema_version") != "forex.m31.protocol-receipt.v1" or receipt.get("protocol_sha256") != "sha256:" + hashlib.sha256(raw).hexdigest(): raise SystemExit("M31 capture refused: protocol receipt mismatch")
from_utc, to_utc = protocol["interval"]["from_utc"], protocol["interval"]["to_utc"]
if protocol["interval"].get("bounds") != "inclusive/exclusive" or not utc(from_utc) < utc(to_utc) or (utc(to_utc) - utc(from_utc)).total_seconds() > 86400: raise SystemExit("M31 capture refused: protocol interval is invalid")
if utc(to_utc) > datetime.now(timezone.utc): raise SystemExit("M31 capture refused: declared interval has not ended")
import subprocess
if receipt.get("git_revision") != subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip(): raise SystemExit("M31 capture refused: protocol revision differs from evaluator revision")
path.write_bytes(raw)
PY
cp -- "$protocol_directory/receipt.json" "$bundle/protocol-receipt.json"

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
names = ("protocol.json", "protocol-receipt.json", "completeness.json", "lifecycle.json", "broker-history.json", "scorecard.json", "revision.txt")
manifest = {"schema_version":"forex.m31.evidence-bundle.v1","milestone_id":"M31","captured_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),"git_revision":(bundle / "revision.txt").read_text().strip(),"observed_result":"FOREX_M31_EVIDENCE_CAPTURED","execution_authority":False,"artifacts":[{"path":name,"sha256":"sha256:" + hashlib.sha256((bundle / name).read_bytes()).hexdigest()} for name in names]}
(bundle / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
PY
bash scripts/verify_m31_evidence.sh "$bundle"
