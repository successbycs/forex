import base64
import pytest
from forex.bls_n8n_envelope import BLSN8nEnvelopeError, build_observation, parse_handoff_json


def handoff():
    return {"capture_id":"bls-1","year":2026,"month":9,"started_at_utc":"2026-09-14T00:00:00Z","completed_at_utc":"2026-09-14T00:00:01Z","status_code":200,"content_type":"text/html","body_base64":base64.b64encode(b"<html>ok</html>").decode(),"body_complete":True}


def test_builds_existing_verified_observation():
    capture_id, raw = build_observation(handoff())
    assert capture_id == "bls-1" and b'"execution_authority":false' in raw


def test_rejects_missing_or_fabricated_handoff_fields():
    value = handoff(); value.pop("status_code")
    with pytest.raises(BLSN8nEnvelopeError): build_observation(value)
    value = handoff(); value["status_code"] = 500
    with pytest.raises(BLSN8nEnvelopeError): build_observation(value)


def test_parser_refuses_duplicate_fields_and_nonfinite_json():
    with pytest.raises(BLSN8nEnvelopeError):
        parse_handoff_json(b'{"capture_id":"a","capture_id":"b"}')
    with pytest.raises(BLSN8nEnvelopeError):
        parse_handoff_json(b'{"value":NaN}')
