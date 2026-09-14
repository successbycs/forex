"""Read-only BLS retained-evidence input to the active primary context contract."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from forex.bls_primary_source_verifier import BLSPrimarySourceVerificationError, verify_bls_primary_source
from forex.primary_event_context import PrimaryEventContextError, qualify_context
class BLSPrimaryContextIntegrationError(RuntimeError): pass
def report_bls_primary_context(*, store_root: Path, contract: dict[str, Any]) -> dict[str, Any]:
 try:
  verified=verify_bls_primary_source(store_root);context=qualify_context(contract=contract,observations=verified["primary_context_observations"])
 except (BLSPrimarySourceVerificationError,PrimaryEventContextError) as exc:raise BLSPrimaryContextIntegrationError("BLS primary context integration refused") from exc
 return {"schema_version":"forex.bls-primary-context-integration.v1","execution_authority":False,"coverage_status":"UNKNOWN","primary_context":context,"verified_bls_source":verified}
