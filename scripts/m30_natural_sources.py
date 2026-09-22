"""Offline provenance joins for natural M30 captures, never execution authority.

This is a source-integrity check, not the formal M30 proof verifier. Original
adapter outputs remain unchanged; the return value references their records.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from forex.m20_spool_page import parse_page


class SourceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SourceError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = value
        return result

    def constant(_):
        raise SourceError('nonfinite JSON value')

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (TypeError, json.JSONDecodeError) as error:
        raise SourceError('invalid source JSON') from error


def read_output(raw, operation, *, tool_id=None):
    outer = strict_json(raw)
    require(isinstance(outer, dict) and outer.get('ok') is True
            and outer.get('operation') == operation, 'fixed operation identity mismatch')
    if tool_id is not None:
        require(outer.get('tool_id') == tool_id, 'fixed adapter identity mismatch')
    result = outer.get('result')
    require(isinstance(result, dict) and result.get('ok') is True
            and type(result.get('exit_code')) is int and result['exit_code'] == 0,
            'fixed operation failed')
    return strict_json(result.get('stdout'))


def same_value(left, right, field):
    require(type(left) is not bool and type(right) is not bool, f'boolean value: {field}')
    if field.endswith('_at_utc'):
        try:
            a, b = (datetime.fromisoformat(v.replace('Z', '+00:00')) for v in (left, right))
        except (TypeError, ValueError, AttributeError) as error:
            raise SourceError(f'invalid timestamp: {field}') from error
        require(a.utcoffset() is not None and b.utcoffset() is not None and a == b,
                f'timestamp mismatch: {field}')
    elif type(left) in (int, float) and type(right) in (int, float):
        require(math.isfinite(left) and math.isfinite(right)
                and math.isclose(left, right, rel_tol=0, abs_tol=1e-10),
                f'numeric mismatch: {field}')
    else:
        require(left == right, f'value mismatch: {field}')


def load_sources(bundle: Path):
    """Check every retained digest and join one source proposal to exact facts.

    Hashes are self-attested integrity, not an external witness. No derived
    execution response, session field, broker result or missing fact is invented.
    """
    require(not bundle.is_symlink() and bundle.is_dir(), 'unsafe bundle path')
    receipt_path = bundle / 'raw-capture-receipt.json'
    require(not receipt_path.is_symlink(), 'unsafe receipt path')
    receipt = strict_json(receipt_path.read_bytes())
    require(isinstance(receipt, dict)
            and receipt.get('schema_version') == 'forex.m30.natural-raw-capture.v1'
            and receipt.get('proof_status') == 'UNVERIFIED_RAW_CAPTURE'
            and receipt.get('execution_authority') is False, 'capture receipt identity mismatch')
    artifacts = receipt.get('artifacts')
    require(isinstance(artifacts, list) and artifacts, 'missing raw artifact inventory')
    raw = {}
    for item in artifacts:
        require(isinstance(item, dict), 'invalid artifact item')
        name = item.get('path')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_.-]+', name)
                and name not in {'.', '..', 'raw-capture-receipt.json'} and name not in raw,
                'unsafe or duplicate artifact name')
        path = bundle / name
        require(not path.is_symlink() and path.is_file(), 'unsafe artifact path')
        data = path.read_bytes()
        require(hashlib.sha256(data).hexdigest() == item.get('sha256'),
                f'artifact digest mismatch: {name}')
        raw[name] = data
    required = {'lifecycle-summary.json', 'natural-entry-facts.json',
                'listener-diagnostics.json', 'listener-status.json',
                'terminal-identity.json', 'watchdog-status.json'}
    require(required <= raw.keys(), 'missing required raw observations')
    pages = sorted(name for name in raw if re.fullmatch(r'spool-page-\d{4}\.json', name))
    require(pages == [f'spool-page-{i:04d}.json' for i in range(len(pages))]
            and pages, 'missing or noncontiguous spool pages')
    release = None
    cursor = None
    matches = []
    for name in pages:
        page_output = read_output(raw[name], 'm20_listener_spool_page', tool_id='forex_t480')
        if cursor is None:
            cursor = page_output.get('after_assessment_sequence')
            require(type(cursor) is int and cursor >= 0, 'invalid first spool cursor')
        page = parse_page(raw[name], after_assessment_sequence=cursor)
        require(release is None or release == page['listener_release_id'],
                'cross-release spool join')
        release = page['listener_release_id']
        require(page['records'], 'empty captured spool page')
        for sequence, data in page['records']:
            record = strict_json(data)
            assessment = record.get('assessment')
            require(isinstance(assessment, dict), 'missing source assessment')
            proposal = assessment.get('proposal')
            require(isinstance(proposal, dict), 'missing source proposal')
            # Candle-keyed proposals recur on later assessments; only the
            # receipt's exact sequence may bind the persisted entry snapshot.
            if (proposal.get('proposal_id') == receipt.get('proposal_id')
                    and sequence == receipt.get('source_match', {}).get('assessment_sequence')):
                matches.append((name, sequence, data, record))
        cursor = page['records'][-1][0]
    require(len(matches) == 1, 'source proposal absent or duplicated')
    name, sequence, data, source = matches[0]
    require(receipt.get('source_match') == {
        'page': name, 'assessment_sequence': sequence,
        'raw_sha256': 'sha256:' + hashlib.sha256(data).hexdigest()}, 'receipt source binding mismatch')
    assessment = source['assessment']
    require(assessment.get('server') == 'GOMarketsMU-Demo'
            and assessment.get('symbol') == 'EURUSD', 'source is not Demo EURUSD')
    proposal = assessment['proposal']
    require({'proposal_id', 'session_id', 'snapshot_id', 'decision_snapshot_sha256',
             'decision_at_utc', 'expires_at_utc', 'action', 'proposed_entry', 'stop_loss',
             'take_profit', 'notional_usd', 'confidence', 'rationale', 'selected_timeframe',
             'strategy_version', 'decision_key', 'decision_candle_closed_at_utc'} <= proposal.keys(),
            'missing source proposal fields')
    snapshot = assessment.get('decision_snapshot')
    require(isinstance(snapshot, dict), 'missing source snapshot')
    body = {key: value for key, value in snapshot.items()
            if key not in {'snapshot_id', 'payload_sha256'}}
    digest = 'sha256:' + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(digest == snapshot.get('payload_sha256') == proposal.get('decision_snapshot_sha256')
            and snapshot.get('snapshot_id') == proposal.get('snapshot_id'),
            'source snapshot digest or identity mismatch')
    require(snapshot['snapshot_id'] == str(uuid5(NAMESPACE_URL, f"{proposal['proposal_id']}:{digest}")),
            'snapshot UUID does not bind proposal and digest')
    rows = read_output(raw['lifecycle-summary.json'], 'forex_m20_lifecycle_summary',
                       tool_id='forex_postgres_pgvector_t480')
    facts = read_output(raw['natural-entry-facts.json'], 'forex_m30_natural_entry_facts',
                        tool_id='forex_postgres_pgvector_t480')
    require(isinstance(rows, list) and isinstance(facts, list), 'ledger output is not rows')
    selected = [row for row in rows if isinstance(row, dict)
                and row.get('proposal_id') == receipt['proposal_id']]
    entries = [entry for entry in facts if isinstance(entry, dict)
               and entry.get('proposal', {}).get('proposal_id') == receipt['proposal_id']]
    require(len(selected) == len(entries) == 1, 'ambiguous or missing ledger identity')
    row, entry = selected[0], entries[0]
    require(all(isinstance(entry.get(key), dict) for key in ('proposal', 'attempt', 'session', 'selection')),
            'invalid entry fact shape')
    persisted, attempt = entry['proposal'], entry['attempt']
    require(row.get('attempt_id') == attempt.get('attempt_id') == receipt.get('attempt_id')
            and attempt.get('proposal_id') == proposal['proposal_id'], 'attempt binding mismatch')
    require(row.get('session_id') == attempt.get('session_id') == proposal.get('session_id')
            == entry['session'].get('session_id'), 'session binding mismatch')
    require(row.get('application_revision') == persisted.get('application_revision')
            == receipt.get('application_revision'), 'runtime revision mismatch')
    require(row.get('configuration_fingerprint') == persisted.get('configuration_fingerprint')
            == assessment.get('configuration_fingerprint'), 'configuration binding mismatch')
    for field, value in proposal.items():
        if field == 'snapshot_id':
            require(value == row.get(field), 'lifecycle snapshot identity mismatch')
        else:
            require(field in persisted, f'missing persisted proposal field: {field}')
            same_value(value, persisted[field], field)
    require(row.get('decision_snapshot_sha256') == row.get('snapshot_payload_sha256') == digest,
            'lifecycle snapshot digest mismatch')
    same_value(snapshot.get('captured_at_utc'), row.get('snapshot_captured_at_utc'), 'snapshot_captured_at_utc')
    for field in ('proposed_entry', 'stop_loss', 'take_profit'):
        try:
            require(type(row.get(field)) in (str, int, float), f'invalid lifecycle price: {field}')
            same_value(proposal[field], float(row[field]), field)
        except (ValueError, TypeError) as error:
            raise SourceError(f'invalid lifecycle price: {field}') from error
    for field in ('decision_at_utc', 'action'):
        same_value(proposal[field], row.get(field), field)
    same_value(proposal['expires_at_utc'], row.get('proposal_expires_at_utc'), 'expires_at_utc')
    same_value(attempt.get('submitted_at_utc'), row.get('submitted_at_utc'), 'submitted_at_utc')
    selection = entry['selection']
    context = snapshot.get('market_context')
    selection_fields = {'market_regime', 'market_regime_reason', 'selected_strategy_id',
                        'selection_status', 'strategy_rule_version', 'cost_coverage_status',
                        'estimated_round_trip_cost_aud', 'minimum_net_profit_aud',
                        'expected_net_profit_at_take_profit_aud', 'entry_spread_cost_aud',
                        'expected_exit_spread_cost_aud', 'commission_allowance_aud',
                        'slippage_allowance_aud', 'expected_swap_aud',
                        'projected_gross_profit_at_take_profit_aud'}
    require(isinstance(context, dict) and selection_fields <= context.keys()
            and selection_fields <= selection.keys(), 'missing source selection fields')
    for field in selection_fields:
        same_value(context[field], selection[field], field)
    require(selection.get('proposal_id') == proposal['proposal_id']
            == selection.get('trade_owner_id'), 'selection proposal binding mismatch')
    for field in ('selected_strategy_id', 'trade_owner_strategy_id'):
        require(selection.get(field) == row.get(field), f'selection binding mismatch: {field}')
    return {'receipt': receipt, 'source': source, 'entry': entry, 'lifecycle': row,
            'listener_release_id': release}
