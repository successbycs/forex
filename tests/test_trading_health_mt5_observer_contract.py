import json
from pathlib import Path

ROOT = Path("config/schemas")

def test_release_a_schemas_are_strict_no_secret_contracts():
    candidate=json.loads((ROOT/"trading-health-mt5-observer-candidate.schema.json").read_text())
    receipt=json.loads((ROOT/"trading-health-mt5-observer-bootstrap-receipt.schema.json").read_text())
    refusal=json.loads((ROOT/"trading-health-mt5-observer-bootstrap-refusal.schema.json").read_text())
    for schema in (candidate,receipt,refusal):
        assert schema["additionalProperties"] is False
        serialized=json.dumps(schema).casefold()
        assert "password" not in serialized and "credential" not in serialized
    assert candidate["properties"]["broker_mutation"]["const"] == "NONE"
    assert candidate["properties"]["entry_eligible"]["const"] is False
    assert refusal["properties"]["refusal_reason"]["enum"]

def test_existing_witness_schema_stays_no_order_only():
    witness=json.loads((ROOT/"trading-health-mt5-observer-witness.schema.json").read_text())
    assert witness["properties"]["order_submission"]["const"] == "STRUCTURALLY_UNAVAILABLE"
