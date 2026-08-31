"""Fixed M6 closed EUR/USD history probe for M15, H1, and D1 on the T480."""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5


SYMBOL = "EURUSD"
TIMEFRAMES = (("M15", mt5.TIMEFRAME_M15, 720), ("H1", mt5.TIMEFRAME_H1, 720), ("D1", mt5.TIMEFRAME_D1, 365))


def utc(value: int) -> str:
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
        datasets = []
        capture_cutoff = int(datetime.now(timezone.utc).timestamp())
        for name, timeframe, count in TIMEFRAMES:
            # Retrieve a fixed small surplus, then reject broker-clock future bars.
            rates = mt5.copy_rates_from_pos(SYMBOL, timeframe, 1, count + 32)
            if rates is None:
                raise SystemExit(f"expected closed EURUSD {name} bars")
            rates = [rate for rate in rates if int(rate["time"]) < capture_cutoff][-count:]
            if len(rates) != count:
                raise SystemExit(f"expected exactly {count} closed EURUSD {name} bars before capture cutoff")
            rows, previous = [], None
            for rate in rates:
                timestamp = int(rate["time"])
                if previous is not None and timestamp <= previous:
                    raise SystemExit(f"EURUSD {name} bars are not strictly chronological")
                previous = timestamp
                row = {"time_utc": utc(timestamp), "open": float(rate["open"]), "high": float(rate["high"]), "low": float(rate["low"]), "close": float(rate["close"]), "volume": int(rate["tick_volume"])}
                if min(row["open"], row["high"], row["low"], row["close"]) <= 0 or row["low"] > min(row["open"], row["close"]) or row["high"] < max(row["open"], row["close"]):
                    raise SystemExit(f"EURUSD {name} has invalid OHLC")
                rows.append(row)
            encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
            datasets.append({
                "timeframe": name,
                "closed_bar_count": len(rows),
                "first_bar_utc": rows[0]["time_utc"],
                "last_bar_utc": rows[-1]["time_utc"],
                "bars_sha256": hashlib.sha256(encoded).hexdigest(),
                "quality_label": "CLOSED_OHLC_VALIDATED",
                "capture_cutoff_utc": utc(capture_cutoff),
                "bars_encoding": "gzip+base64-json",
                "bars_payload": base64.b64encode(gzip.compress(encoded)).decode("ascii"),
            })
        print(json.dumps({"schema_version": "forex.mt5-multitimeframe.v1", "server": account.server, "symbol": SYMBOL, "datasets": datasets, "probe_sha256": os.environ.get("FOREX_M6_PROBE_SHA256", "UNDECLARED")}, separators=(",", ":")))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("expected terminal path")
    main(sys.argv[1])
