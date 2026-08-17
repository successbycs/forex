#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python3 -m compileall -q src scripts
python3 scripts/validate_config.py --root .
python3 scripts/forex_milestones.py validate
python3 scripts/check_no_secrets.py --root .
python3 scripts/t480_adapter.py describe-requirements >/dev/null
python3 -m pytest -q

echo "FOREX_REPOSITORY_VERIFICATION_OK"
