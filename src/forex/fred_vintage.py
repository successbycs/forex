"""Bounded FRED/ALFRED vintage-observation client for M8.

This deliberately exposes one declared series only. It is not a generic data
download surface and it never makes a trading decision.
"""
from __future__ import annotations

import json
import os
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SERIES_ID = "CPIAUCSL"
API_URL = "https://api.stlouisfed.org/fred/series/observations"


class VintageDataError(ValueError):
    """Raised when a response cannot support point-in-time replay."""


def require_api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise VintageDataError("FRED_API_KEY is required for the M8 vintage-data proof")
    return key


def observation_url(decision_date: str, api_key: str) -> str:
    cutoff = date.fromisoformat(decision_date).isoformat()
    query = urlencode({
        "series_id": SERIES_ID,
        "api_key": api_key,
        "file_type": "json",
        "realtime_start": cutoff,
        "realtime_end": cutoff,
        "observation_end": cutoff,
        "sort_order": "asc",
    })
    return f"{API_URL}?{query}"


def normalise_payload(payload: dict, decision_date: str) -> dict:
    cutoff = date.fromisoformat(decision_date).isoformat()
    if payload.get("realtime_start") != cutoff or payload.get("realtime_end") != cutoff:
        raise VintageDataError("FRED response is not bound to the requested vintage date")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise VintageDataError("FRED response contains no observations")
    normalised = []
    for row in observations:
        if row.get("date", "") > cutoff or row.get("realtime_start", "") > cutoff:
            raise VintageDataError("FRED response contains future information")
        if row.get("value") in {None, "."}:
            continue
        normalised.append({
            "series_id": SERIES_ID,
            "observation_date": row["date"],
            "value": float(row["value"]),
            "vintage_start": row["realtime_start"],
            "vintage_end": row["realtime_end"],
            "decision_cutoff": cutoff,
        })
    if not normalised:
        raise VintageDataError("FRED response contains no usable observations")
    return {"series_id": SERIES_ID, "decision_cutoff": cutoff, "observations": normalised}


def fetch_vintage_sample(decision_date: str) -> dict:
    key = require_api_key()
    request = Request(observation_url(decision_date, key), headers={"User-Agent": "forex-m8-vintage/1.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return normalise_payload(payload, decision_date)
