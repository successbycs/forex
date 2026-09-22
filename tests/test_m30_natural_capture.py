import subprocess
from unittest.mock import patch

import pytest

from scripts.m30_natural_capture import read_operation
from scripts import postgres_pgvector_adapter as adapter


def test_capture_preserves_partial_timeout_bytes(tmp_path):
    error = subprocess.TimeoutExpired('fixed read', 60, output=b'partial', stderr=b'timeout')
    with patch('scripts.m30_natural_capture.subprocess.run', side_effect=error):
        with pytest.raises(subprocess.TimeoutExpired):
            read_operation(tmp_path, 'observation.json', ['scripts/t480_adapter.py'])
    assert (tmp_path / 'observation.json').read_bytes() == b'partial'
    assert (tmp_path / 'observation.json.stderr').read_bytes() == b'timeout'


def test_capture_does_not_overwrite_existing_observation(tmp_path):
    (tmp_path / 'observation.json').write_bytes(b'original')
    result = subprocess.CompletedProcess([], 0, b'{}', b'')
    with patch('scripts.m30_natural_capture.subprocess.run', return_value=result):
        with pytest.raises(FileExistsError):
            read_operation(tmp_path, 'observation.json', ['scripts/t480_adapter.py'])
    assert (tmp_path / 'observation.json').read_bytes() == b'original'


def test_entry_facts_query_is_bounded_demo_read_only():
    with patch.object(adapter, 'remote', return_value={'ok': True, 'exit_code': 0, 'stdout': '[]'}) as remote:
        adapter.m30_natural_entry_facts()
    query = remote.call_args.args[0]
    assert "s.server='GOMarketsMU-Demo'" in query
    assert "s.instrument='EURUSD'" in query
    assert "interval '24 hours'" in query and 'LIMIT 1000' in query
    aggregate = query.split('(SELECT json_build_object', 1)[1].split(') session_reservations', 1)[0]
    assert 'sum(ap.notional_usd)' in aggregate and 'count(*)' in aggregate
    assert 'aa.session_id=s.session_id' in aggregate
    assert 'status' not in aggregate and 'submitted_at' not in aggregate
    assert not any(word in query.upper() for word in ('INSERT ', 'DELETE ', 'UPDATE ', 'ALTER '))


def test_entry_facts_targeted_query_is_exact_and_bounded():
    proposal_id = 'a88ae86c-6b7e-5a03-9367-157389f0f0b5'
    with patch.object(adapter, 'remote', return_value={'ok': True, 'exit_code': 0, 'stdout': '[]'}) as remote:
        adapter.m30_natural_entry_facts(proposal_id)
    query = remote.call_args.args[0]
    assert "p.proposal_id='a88ae86c-6b7e-5a03-9367-157389f0f0b5'" in query
    assert 'LIMIT 2' in query
    assert not any(word in query.upper() for word in ('INSERT ', 'DELETE ', 'UPDATE ', 'ALTER '))


def test_entry_facts_actual_encoded_transport_is_below_limit():
    result = subprocess.CompletedProcess([], 0, '[]', '')
    with patch.object(adapter.subprocess, 'run', return_value=result) as run:
        adapter.m30_natural_entry_facts()
    assert len(run.call_args.args[0][-1]) < 7500
