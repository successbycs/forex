"""Fixed ECB SDMX macro sample client for M9."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SERIES_KEY = "M.U2.N.000000.4.ANR"  # Euro-area HICP annual rate of change
API_URL = f"https://data-api.ecb.europa.eu/service/data/ICP/{SERIES_KEY}"


class EcbMacroError(ValueError):
    pass


def sample_url(start_period: str = "2024-01", end_period: str = "2024-02") -> str:
    return API_URL + "?" + urlencode({"startPeriod": start_period, "endPeriod": end_period, "format": "csvdata", "includeHistory": "true"})


def normalise_csv(raw: bytes, retrieved_at: str) -> dict:
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    if not rows or any(row.get("KEY") != f"ICP.{SERIES_KEY}" for row in rows):
        raise EcbMacroError("ECB response does not match the declared ICP series")
    if any(not row.get("TIME_PERIOD") or row.get("OBS_VALUE") in {None, ""} for row in rows):
        raise EcbMacroError("ECB response has incomplete observations")
    if not retrieved_at.endswith("Z"):
        raise EcbMacroError("retrieval timestamp must be UTC")
    return {
        "source_id": "ecb-data-portal-euro-macro",
        "series_key": f"ICP.{SERIES_KEY}",
        "title": rows[0].get("TITLE", ""),
        "retrieved_at_utc": retrieved_at,
        "include_history": True,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "observations": [{"period": row["TIME_PERIOD"], "value": float(row["OBS_VALUE"]), "status": row.get("OBS_STATUS", "")} for row in rows],
    }


def fetch_sample() -> dict:
    request = Request(sample_url(), headers={"User-Agent": "forex-m9-ecb/1.0"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return normalise_csv(raw, now)
