"""Fail-closed observation checks for Chris's single September 23 correction."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json

SCOPE = '4b12a2cebac68fadc4009c52f46e1cda20bd3c731ef94428ed2b47a2d29faabf'
POSITIONS = {43135808, 43135809, 43135810, 43135811}
SOURCE_SHA256 = '068bb6d05046fbf018362c22fcd35cbdc6920f3b520948d0a57d8f5096dbcf18'


def validate_source(raw, expected_deals):
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Original incident evidence digest differs')
    history = json.loads(json.loads(raw)['result']['stdout'])
    deals = [d for d in history['deals'] if d.get('position_id') in POSITIONS]
    if sorted(deals,key=lambda d:d['ticket']) != sorted(expected_deals,key=lambda d:d['ticket']):
        raise ValueError('SQL incident deals differ from original evidence')


def validate_observations(history, account, status, expected_deals, *, now=None):
    now = now or datetime.now(timezone.utc)
    def fresh(stamp):
        age = (now - datetime.fromisoformat(stamp.replace('Z', '+00:00'))).total_seconds()
        return 0 <= age < 30
    if (history.get('ok') is not True or history.get('complete') is not True
            or history.get('server') != 'GOMarketsMU-Demo' or history.get('currency') != 'AUD'
            or history.get('account_scope_sha256') != SCOPE
            or history.get('broker_timestamp_offset_seconds') != 10800
            or not fresh(history.get('captured_at_utc', ''))):
        raise ValueError('Incident requires fresh complete bound Demo history')
    if (account.get('ok') is not True or account.get('server') != 'GOMarketsMU-Demo'
            or account.get('currency') != 'AUD' or account.get('account_scope_sha256') != 'sha256:' + SCOPE
            or account.get('open_positions') != 0 or account.get('pending_orders') != 0):
        raise ValueError('Incident requires the exact flat Demo account with no pending orders')
    if (status.get('state') != 'MAINTENANCE_HOLD'
            or not fresh(status.get('heartbeat_at_utc', ''))):
        raise ValueError('Incident requires a fresh acknowledged maintenance hold')
    for observation in (history, account):
        if any(Decimal(str(observation.get(key))) != Decimal('100960.81') for key in ('balance', 'equity')):
            raise ValueError('Incident broker balance/equity changed')
    actual = [d for d in history['deals'] if d.get('position_id') in POSITIONS]
    if len(actual) != 8 or sorted(actual, key=lambda d: d['ticket']) != sorted(expected_deals, key=lambda d: d['ticket']):
        raise ValueError('Incident deals differ from the reviewed source')
    if sum(Decimal(str(d[key])) for d in actual for key in ('profit','commission','swap','fee')) != Decimal('-28.64'):
        raise ValueError('Incident net loss differs')
