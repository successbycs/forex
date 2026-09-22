"""Read-only report shared by terminal and future presentation surfaces."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import textwrap

from scripts.m20_listener_evidence_view import latest_assessment, lifecycle_rows, _run_json
from scripts.m20_trade_ledger_dashboard import _state, _pnl


def local_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(
            ZoneInfo('Pacific/Auckland')).strftime('%d/%m %H:%M:%S %Z')
    except (ValueError, TypeError, AttributeError):
        return 'UNKNOWN'


def collect(status_reader, root, python):
    def account_reader():
        return _run_json([python, str(root / 'scripts/t480_adapter.py'), 'execute',
                          '--operation', 'm20_listener_account_identity'],
                         timeout=8, label='account observation')

    def timed(reader):
        try:
            data = reader()
        except Exception as error:
            data = {'error': str(error)}
        return {'fetched_at_utc': datetime.now(timezone.utc).isoformat(), 'data': data}

    readers = dict(status=status_reader, assessment=latest_assessment,
                   account=account_reader, ledger=lifecycle_rows)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {key: pool.submit(timed, reader) for key, reader in readers.items()}
        sources = {key: job.result() for key, job in jobs.items()}
    return build_report(sources)


def build_report(sources):
    def data(name):
        return sources.get(name, {}).get('data')
    status = data('status') if isinstance(data('status'), dict) else {}
    result = status.get('last_result') or {}
    proposal = result.get('proposal') or {}
    latest = data('assessment') if isinstance(data('assessment'), dict) else {}
    assessment = latest.get('assessment') or {}
    matched = (latest.get('observation') == 'AVAILABLE' and
               bool(proposal.get('proposal_id')) and
               (assessment.get('proposal') or {}).get('proposal_id') == proposal.get('proposal_id'))
    account = data('account') if isinstance(data('account'), dict) else {}
    account_ok = (account.get('ok') is True and account.get('server') == 'GOMarketsMU-Demo'
                  and account.get('currency') == 'AUD')
    attention = []
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(
            status['heartbeat_at_utc'].replace('Z', '+00:00'))).total_seconds()
        if age < 0 or age >= 30:
            attention.append(f'STALE listener heartbeat: {age:.0f}s age; recorded state is historical')
    except (KeyError, ValueError, TypeError):
        age = None
        attention.append('Listener freshness UNKNOWN')
    for name, source in sources.items():
        value = source.get('data')
        error = value.get('error') if isinstance(value, dict) else None
        if isinstance(value, list) and value and isinstance(value[0], dict):
            error = value[0].get('error')
        if isinstance(value, dict) and value.get('state') == 'UNAVAILABLE':
            error = value.get('detail') or 'UNAVAILABLE'
        if error:
            attention.append(f'{name}: UNAVAILABLE — {error}')
    rows = data('ledger')
    rows = rows if isinstance(rows, list) else []
    trades = []
    for row in rows:
        if not isinstance(row, dict) or row.get('error'):
            continue
        state = _state(row, None)
        pnl = _pnl(row) if state in ('SOLD / VERIFIED', 'REJECTED', 'RECONCILIATION ERROR') else 'Pending'
        trades.append({**row, 'display_state': state, 'display_pnl': pnl})
    return {'schema_version': 'forex.listener-operator-report.v1', 'sources': sources,
            'status': status, 'decision': result, 'attention': attention, 'heartbeat_age_seconds': age,
            'assessment_join': 'MATCHED' if matched else 'UNKNOWN / proposal mismatch or unavailable',
            'risk': assessment.get('risk_policy') if matched else None,
            'account': account if account_ok else {}, 'trades': trades}


def render_workflow(report, width=100):
    def val(value):
        return 'UNKNOWN' if value is None or value == '' else str(value)
    status, result = report['status'], report['decision']
    p, m = result.get('proposal') or {}, result.get('assessment_metrics') or {}
    q, selection = status.get('quote') or {}, result.get('strategy_selection') or {}
    risk, account = report.get('risk') or {}, report['account']
    lines = ['EUR/USD DEMO — operator workflow',
             f"Listener: {val(status.get('state'))} | heartbeat {local_time(status.get('heartbeat_at_utc'))}",
             f"Broker positions observed: {val(account.get('open_positions'))} | balance {val(account.get('balance'))} AUD",
             *[f'ATTENTION: {item}' for item in report['attention']],
             'Active / unresolved trades (ledger observations):']
    active = [r for r in report['trades'] if r.get('display_state') == 'MONITORING']
    unresolved = [r for r in report['trades'] if r.get('display_state') not in ('MONITORING', 'SOLD / VERIFIED', 'REJECTED')]
    lines.append(f'  Historical/unresolved ledger rows: {len(unresolved)} (not proof of current exposure).')
    for row in active:
        lines.append(f"  {val(row.get('action'))} | {row['display_state']} | attempt {val(row.get('attempt_id'))}")
    if not active:
        lines.append('  No active rows available in this report; check source warnings and broker observation.')
    lines.extend(['', '1. PRICE & CANDLE',
                  f"Bid / ask: {val(q.get('bid'))} / {val(q.get('ask'))} | spread {val(m.get('spread_points'))} points (assessment)",
                  f"Closed M1: {local_time(p.get('decision_candle_closed_at_utc') or m.get('last_closed_at_utc'))} | close {val(m.get('last_close'))} | previous {val(m.get('previous_close'))}",
                  'Forming candle OHLC: NOT AVAILABLE from this status source.',
                  '', '2. ASSESSMENT'])
    for s in result.get('strategy_assessments') or []:
        lines.append(f"{val(s.get('label'))}: {val(s.get('signal'))} — {val(s.get('reason'))}")
    if not result.get('strategy_assessments'):
        lines.append('Strategy assessments: UNKNOWN')
    lines.extend([f"Owner: {val(selection.get('selected_strategy_id'))} | regime {val(selection.get('market_regime'))}",
                  '', '3. DECISION & CHECKS',
                  f"{val(p.get('action'))}: {val(p.get('rationale'))}",
                  f"Risk entry permission: {val(risk.get('entry_allowed'))} | pause {val(risk.get('pause_reason'))}",
                  f"Assessment join: {report['assessment_join']}",
                  f"Cost gate: {val(selection.get('cost_coverage_status'))}",
                  f"Plan: entry {val(p.get('proposed_entry'))} | size {val(p.get('volume_lots'))} lots | SL {val(p.get('stop_loss'))} | TP {val(p.get('take_profit'))}",
                  '', '4. EXECUTION & PROTECTION',
                  f"This proposal {val(p.get('proposal_id'))}: {val((result.get('execution') or {}).get('status'))}",
                  f"Monitor: {val((status.get('monitor') or {}).get('state'))}",
                  f"Protection observation: {val(status.get('protection_observation'))}"])
    protection = status.get('open_position_protection') or {}
    if protection:
        lines.append(f"Retained record only: ticket {val(protection.get('ticket'))} | SL {val(protection.get('stop_loss'))} | TP {val(protection.get('take_profit'))}; not a fresh broker protection check.")
    lines.extend(['', '5. CLOSE & RECONCILIATION',
                  f"Latest decision: {val((result.get('reconciliation') or {}).get('status'))}"])
    for row in sorted(report['trades'], key=lambda r: str(r.get('submitted_at_utc') or ''), reverse=True)[:10]:
        lines.extend([f"{local_time(row.get('submitted_at_utc'))} {val(row.get('action'))} | {row['display_state']} | net {row['display_pnl']}",
                      f"  Strategy {val(row.get('trade_owner_strategy_id') or row.get('selected_strategy_id'))} | closed {local_time(row.get('closed_at_utc'))}",
                      f"  Entry {val(row.get('actual_entry_price') or row.get('proposed_entry'))} | exit {val(row.get('exit_price'))} | reason {val(row.get('close_reason') or row.get('reconciliation_reason') or (row.get('rejection_context') or {}).get('broker_comment'))} | attempt {val(row.get('attempt_id'))}"])
        if row.get('reconciliation_reason'):
            lines.append(f"  Reconciliation detail: {row['reconciliation_reason']}")
    lines.extend(['', 'SOURCE FRESHNESS — fetch times are not trade or candle times'])
    for name, source in report['sources'].items():
        d = source.get('data')
        error = d.get('error') or d.get('detail') if isinstance(d, dict) else None
        if isinstance(d, list) and d and isinstance(d[0], dict):
            error = d[0].get('error')
        lines.append(f"{name}: fetched {local_time(source.get('fetched_at_utc'))}" + (f" | {error}" if error else ''))
    return '\n'.join('\n'.join(textwrap.wrap(line, width=max(40, width), subsequent_indent='  ')) if line else '' for line in lines)
