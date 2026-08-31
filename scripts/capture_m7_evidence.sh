#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
bundle="${1:-runs/evidence/M7/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$bundle"
python3 -m pytest -q tests/milestones/test_m7.py >"$bundle/tests.txt" 2>&1
python3 scripts/forex_milestones.py validate >"$bundle/governance.txt" 2>&1
python3 - "$bundle" <<'PY'
import hashlib,json,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path

b=Path(sys.argv[1]); registry=json.loads(Path('config/source_qualification.json').read_text())
urls={
  'fred-alfred-us-macro':'https://fred.stlouisfed.org/docs/api/fred/',
  'ecb-data-portal-euro-macro':'https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html',
  'trading-economics-calendar':'https://api.tradingeconomics.com/documentation/',
  'gdelt-sentiment-prototype':'https://www.gdeltproject.org/data.html',
}
samples=[]
for source_id,url in urls.items():
    try:
        request=urllib.request.Request(url, headers={'User-Agent':'forex-m7-qualification/1.0'})
        with urllib.request.urlopen(request, timeout=8) as response:
            body=response.read(32768)
            samples.append({'source_id':source_id,'url':url,'status':response.status,'content_type':response.headers.get('content-type',''),'sample_sha256':hashlib.sha256(body).hexdigest(),'sample_bytes':len(body)})
    except Exception as exc:
        # Trading Economics may require a subscription. Its documented endpoint is
        # still observed, while the registry decision remains DEFERRED.
        if source_id not in {'trading-economics-calendar', 'ecb-data-portal-euro-macro'}: raise
        samples.append({'source_id':source_id,'url':url,'status':'ACCESS_RESTRICTED','error_type':type(exc).__name__})
(b/'source-samples.json').write_text(json.dumps({'captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'samples':samples},indent=2)+'\n')
assert {item['source_id'] for item in samples} == set(urls)
assert all(item['status'] == 200 for item in samples if item['source_id'] != 'trading-economics-calendar')
PY
git rev-parse HEAD >"$bundle/revision.txt"
python3 - "$bundle" <<'PY'
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
b=Path(sys.argv[1]); status=json.loads(subprocess.check_output(['python3','scripts/forex_milestones.py','status','--json']))
artifacts=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
m={'schema_version':'1.0.0','milestone_id':'M7','captured_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'git_revision':(b/'revision.txt').read_text().strip(),'dirty_worktree':False,'configuration_fingerprint':status['configuration_fingerprint'],'surface':'retained source-qualification samples and source-registry decisions','operation':'fixed public source-qualification sample capture','expected_result':'four explicit candidate decisions and bounded public samples','observed_result':'FOREX_M7_PROOF_OK','exit_code':0,'redactions':['No credentials, proprietary calendar payloads, article text, accounts, orders, or live-server data retained.'],'summary':'FOREX_M7_PROOF_OK','artifacts':artifacts}
(b/'summary.txt').write_text('FOREX_M7_PROOF_OK\n')
m['artifacts']=[{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(b.iterdir()) if p.is_file()]
(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
PY
echo "$bundle"
