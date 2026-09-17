# Evidence Brief: M30 MT5 terminal identity diagnostic

## Decision

Decide whether a fixed read-only MT5 identity diagnostic is the smallest safe
way to investigate why GUI Algo Trading and the listener API disagree.

## Proposed claim or hypothesis

The official MetaTrader5 Python API can distinguish the listener terminal's
automated-trading state from its separate external-Python API setting, while
hashed terminal/profile and Windows-session identities can identify a separate
interactive terminal session.

## Context

- Instrument: EUR/USD.
- Environment: GOMarketsMU-Demo on T480.
- Timeframe: M1; no strategy, price, or risk rule is involved.
- Intended use: unblock M30 terminal-permission diagnosis.

## Evidence reviewed

| Source | Type | Finding | Limitation |
|---|---|---|---|
| [MQL5 terminal_info](https://www.mql5.com/en/docs/python_metatrader5/mt5terminalinfo_py) | Official API | The Python API exposes terminal connection, trade_allowed, tradeapi_disabled, executable path, and data path. | It reports state; it does not change it. |
| [MT5 automated-trading settings](https://www.metatrader5.com/en/terminal/help/algotrading/trade_robots_indicators) | Official platform documentation | Automatic terminal trading and external Python API trading are separate controls. | It does not identify a specific Windows session. |

## Findings

### Evidence-supported

- The official API can check the required terminal state. Confidence: high.
- A read-only path/session comparison can be collected without trading.
  Confidence: high.

### Reasonable inference

- The Session-2 GUI and Session-0 scheduled listener are distinct MT5 contexts.
  The fixed observation at 2026-09-17T09:06Z found those two sessions and the
  listener API continued to report trade_allowed false.

### Rejected claim

- Playwright can resolve this state. It controls browser pages, not native MT5.

## Recommendation

Create and execute the fixed read-only diagnostic. It completed successfully;
the next action is an operator change to the Session-0 terminal/profile, not a
strategy or broker change.
