"""Retain original natural-listener evidence without assessing or trading.

Use --raw-only to retain observations during development. By default a clean,
committed collector runs targeted checks and the separate offline proof verifier.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from forex.m20_spool_page import parse_page


def read_operation(bundle, name, arguments):
    try:
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT,
                                capture_output=True, timeout=60)
    except subprocess.TimeoutExpired as error:
        for suffix, raw in [('', error.stdout), ('.stderr', error.stderr)]:
            with (bundle / (name + suffix)).open('xb') as handle:
                handle.write(raw or b'')
        raise
    with (bundle / name).open('xb') as handle:
        handle.write(result.stdout)
    if result.stderr:
        with (bundle / (name + '.stderr')).open('xb') as handle:
            handle.write(result.stderr)
    if result.returncode:
        raise ValueError(f'{name}: fixed read failed; original output retained')
    outer = json.loads(result.stdout)
    if outer.get('ok') is not True or outer.get('result', {}).get('ok') is not True:
        raise ValueError(f'{name}: unsuccessful adapter observation')
    return result.stdout, json.loads(outer['result']['stdout'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proposal_id', type=UUID)
    parser.add_argument('--after-assessment-sequence', type=int, default=0)
    parser.add_argument('--max-pages', type=int, default=250)
    parser.add_argument('--raw-only', action='store_true', help='retain unverified original observations only')
    args = parser.parse_args()
    if args.after_assessment_sequence < 0 or not 1 <= args.max_pages <= 1000:
        parser.error('nonnegative cursor and 1..1000 pages required')
    if not args.raw_only:
        from m30_natural_evidence import clean
        clean(ROOT)
    bundle = ROOT / 'runs/evidence/M30' / datetime.now(timezone.utc).strftime('natural-raw-%Y%m%dT%H%M%S%fZ')
    bundle.mkdir(parents=True, exist_ok=False)
    print(f'Raw capture: {bundle}', flush=True)
    _, rows = read_operation(bundle, 'lifecycle-summary.json',
                            ['scripts/postgres_pgvector_adapter.py', 'forex-m20-lifecycle-summary'])
    matches = [r for r in rows if r.get('proposal_id') == str(args.proposal_id)]
    if len(matches) != 1 or matches[0].get('lifecycle') != 'CLOSED_MATCHED':
        raise ValueError('exact proposal does not have one matched closed lifecycle')
    row = matches[0]
    _, facts = read_operation(bundle, 'natural-entry-facts.json',
                             ['scripts/postgres_pgvector_adapter.py', 'forex-m30-natural-entry-facts',
                              '--proposal-id', str(args.proposal_id)])
    entries = [entry for entry in facts if entry.get('proposal', {}).get('proposal_id') == str(args.proposal_id)
               and entry.get('attempt', {}).get('attempt_id') == row['attempt_id']]
    if len(entries) != 1:
        raise ValueError('immutable entry facts do not match the exact proposal and attempt')
    cursor = args.after_assessment_sequence
    found = None
    release = None
    for page_number in range(args.max_pages):
        raw, page = read_operation(bundle, f'spool-page-{page_number:04d}.json',
            ['scripts/t480_adapter.py', 'execute', '--operation', 'm20_listener_spool_page',
             '--after-assessment-sequence', str(cursor)])
        # Validate the original page/digests with the existing strict parser.
        parse_page(raw, after_assessment_sequence=cursor)
        if release is not None and page['listener_release_id'] != release:
            raise ValueError('listener release changed during raw capture')
        release = page['listener_release_id']
        import base64
        for record in page.get('records', []):
            captured = json.loads(base64.b64decode(record['raw_base64'], validate=True))
            proposal = captured['assessment']['proposal']
            if (proposal.get('proposal_id') == str(args.proposal_id)
                    and proposal.get('snapshot_id') == row.get('snapshot_id')
                    and proposal.get('decision_snapshot_sha256') == row.get('decision_snapshot_sha256')):
                found = {'page': f'spool-page-{page_number:04d}.json',
                         'assessment_sequence': record['assessment_sequence'],
                         'raw_sha256': record['raw_sha256']}
                break
        if found:
            break
        if not page.get('records'):
            raise ValueError('source spool exhausted without exact proposal/snapshot match')
        cursor = page['records'][-1]['assessment_sequence']
    if not found:
        raise ValueError('bounded page limit reached; retain capture and inspect cursor')
    for operation, filename in [('m20_listener_diagnostics', 'listener-diagnostics.json'),
                                ('m20_listener_status', 'listener-status.json'),
                                ('m20_listener_terminal_identity', 'terminal-identity.json'),
                                ('m20_listener_watchdog_status', 'watchdog-status.json')]:
        read_operation(bundle, filename, ['scripts/t480_adapter.py', 'execute', '--operation', operation])
    receipt = {'schema_version': 'forex.m30.natural-raw-capture.v1',
               'proof_status': 'UNVERIFIED_RAW_CAPTURE', 'execution_authority': False,
               'proposal_id': str(args.proposal_id), 'attempt_id': row['attempt_id'],
               'application_revision': row['application_revision'], 'source_match': found,
               'captured_at_utc': datetime.now(timezone.utc).isoformat(),
               'artifacts': [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                             for p in sorted(bundle.iterdir()) if p.is_file()]}
    with (bundle / 'raw-capture-receipt.json').open('x') as handle:
        json.dump(receipt, handle, indent=2)
    print(json.dumps({'bundle': str(bundle), 'proof_status': receipt['proof_status']}))
    if not args.raw_only:
        from m30_natural_evidence import finalize
        finalize(bundle.resolve(), ROOT)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Natural raw capture incomplete: {error}', file=sys.stderr)
        raise SystemExit(2)
