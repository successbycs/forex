"""Fixed M3 EUR/USD H1 historical-depth probe for the Windows T480."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5


SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H1
TIMEFRAME_NAME = "H1"
# This is deliberately a fixed ceiling, not a caller-provided query size.
REQUESTED_CLOSED_BARS = 100_000
# Some broker terminals reject an over-large single request instead of returning
# their available history.  These fixed descending sizes distinguish that API
# limit from unavailable data without accepting a caller-supplied query.
REQUEST_CANDIDATES = (100_000, 50_000, 30_000, 25_000, 20_000, 19_000, 18_000, 15_000, 10_000, 5_000, 2_000, 720)


def timestamp_utc(value: int) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


def main(terminal_path: str) -> None:
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        if not account or account.server != "GOMarketsMU-Demo":
            raise SystemExit("MT5 is not connected to GOMarketsMU-Demo")
        symbol = mt5.symbol_info(SYMBOL)
        if not symbol or symbol.name != SYMBOL:
            raise SystemExit("required EURUSD symbol is unavailable")
        # Position one excludes the still-forming current H1 candle.
        rates = None
        largest_successful_request = None
        for candidate in REQUEST_CANDIDATES:
            returned = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 1, candidate)
            if returned is not None and len(returned) > 0:
                rates = returned
                largest_successful_request = candidate
                break
        if rates is None:
            raise SystemExit("no closed EURUSD H1 history was returned")

        previous = None
        invalid_ohlc_count = 0
        for rate in rates:
            current = int(rate["time"])
            if previous is not None and current <= previous:
                raise SystemExit("historical bars are not strictly chronological")
            previous = current
            values = (float(rate["open"]), float(rate["high"]), float(rate["low"]), float(rate["close"]))
            if min(values) <= 0 or values[2] > min(values[0], values[3]) or values[1] < max(values[0], values[3]):
                invalid_ohlc_count += 1

        print(json.dumps({
            "schema_version": "forex.mt5-history-depth.v1",
            "server": account.server,
            "symbol": symbol.name,
            "timeframe": TIMEFRAME_NAME,
            "requested_closed_bars": REQUESTED_CLOSED_BARS,
            "largest_successful_request": largest_successful_request,
            "returned_closed_bars": len(rates),
            "first_bar_utc": timestamp_utc(int(rates[0]["time"])),
            "last_bar_utc": timestamp_utc(int(rates[-1]["time"])),
            "request_cap_reached": largest_successful_request == REQUESTED_CLOSED_BARS and len(rates) == REQUESTED_CLOSED_BARS,
            "invalid_ohlc_count": invalid_ohlc_count,
            "probe_sha256": os.environ.get("FOREX_M3_PROBE_SHA256", "UNDECLARED"),
        }, separators=(",", ":")))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("expected terminal path")
    main(sys.argv[1])
