"""Fixed M1 EUR/USD historical-export probe for the Windows T480."""

import base64
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone

import MetaTrader5 as mt5


SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_H1
BAR_COUNT = 720


def main(terminal_path: str) -> None:
    if not mt5.initialize(path=terminal_path):
        raise SystemExit(mt5.last_error())
    try:
        account = mt5.account_info()
        if not account or account.server != "GOMarketsMU-Demo":
            raise SystemExit("MT5 is not connected to GOMarketsMU-Demo")
        symbol = mt5.symbol_info(SYMBOL)
        rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 1, BAR_COUNT)
        if not symbol or symbol.name != SYMBOL:
            raise SystemExit("required EURUSD symbol is unavailable")
        if rates is None or len(rates) != BAR_COUNT:
            raise SystemExit(f"expected exactly {BAR_COUNT} closed EURUSD H1 bars")

        bars = []
        previous_time = None
        for rate in rates:
            timestamp = int(rate["time"])
            if previous_time is not None and timestamp <= previous_time:
                raise SystemExit("historical bars are not strictly chronological")
            previous_time = timestamp
            bar = {
                "time_utc": datetime.fromtimestamp(timestamp, timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "open": float(rate["open"]),
                "high": float(rate["high"]),
                "low": float(rate["low"]),
                "close": float(rate["close"]),
                "volume": int(rate["tick_volume"]),
            }
            if (
                min(bar["open"], bar["high"], bar["low"], bar["close"]) <= 0
                or bar["low"] > min(bar["open"], bar["close"])
                or bar["high"] < max(bar["open"], bar["close"])
            ):
                raise SystemExit("historical bar has invalid OHLC values")
            bars.append(bar)

        raw_bars = json.dumps(bars, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = {
            "server": account.server,
            "symbol": symbol.name,
            "timeframe": "H1",
            "bar_count": len(bars),
            "first_bar_utc": bars[0]["time_utc"],
            "last_bar_utc": bars[-1]["time_utc"],
            "bars_sha256": hashlib.sha256(raw_bars).hexdigest(),
            "bars_encoding": "gzip+base64-json",
            "bars_payload": base64.b64encode(gzip.compress(raw_bars)).decode("ascii"),
        }
        print(json.dumps(payload, separators=(",", ":")))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("expected terminal path")
    main(sys.argv[1])
