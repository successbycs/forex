# M1 — Historical MT5 Demo export proof

M1 uses the catalog-locked read-only path on the Windows T480 to export closed
EUR/USD historical bars from `GOMarketsMU-Demo`.
It is a fixed Python program that returns exactly 720 closed `EURUSD` H1 bars
(about 30 days), together with the connected server, bar range, and a content
hash. The reviewed fixed probe source is installed at the fixed T480-local
path beside `mt5.local.json`; its expected SHA-256 is derived from the committed
probe source. The Python path and SHA-256 are approved in governed
`config/t480.json`; without that interpreter pin, the catalog operation refuses
to execute. It accepts no source, path, or command argument. The raw bars are carried as a `gzip+base64-json` payload so
the bounded export fits through the Windows SSH channel; the hash is calculated
over the uncompressed canonical bar JSON. It initializes the locally installed
MT5 terminal and always shuts it down cleanly; it does not expose a generic
command parameter, credentials, account values, positions, or order methods.

The probe fails closed unless the server is exactly `GOMarketsMU-Demo`, the
symbol is exactly `EURUSD`, and all 720 bars are closed, chronological, and
valid OHLC values. It reads executable paths from the ignored T480-local
`mt5.local.json` file, not from tracked source. The historical export must
identify the Demo server, exact symbol, timeframe, closed-bar range, timestamps,
and source operation. It must not export or persist credentials, account
balances, or any order capability. A fresh tick is not an M1 requirement; it
is a Phase 3 M27 requirement.

Raw evidence and the implementation revision remain required before M1 can be
closed.
