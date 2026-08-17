# MQL5 / MetaTrader 5 knowledge base — link index

Curated links from the MetaTrader "Create your own trading app" developer
email (captured 2026-08-17, source file `Create your own trading app.htm`).
This is a reference index for later research; it does not itself define or
authorize any Forex milestone. See
[mt5-platform-ecosystem.md](mt5-platform-ecosystem.md) for the narrative
description and `forex-m0-foundation-prompt.md` for what is actually in
scope now.

## Language and documentation

- MQL5 language reference / docs: https://www.mql5.com/en/docs
- MetaEditor: https://www.metatrader5.com/en/automated-trading/metaeditor
- Strategy Tester: https://www.metatrader5.com/en/automated-trading/strategy-tester
- MQL5 Storage (Subversion-based version control):
  https://www.metatrader5.com/en/metaeditor/help/mql5storage/mql5storage_working

## Code and articles

- Code Base (free source for indicators, EAs, scripts, libraries):
  https://www.mql5.com/en/code
- Expert articles: https://www.mql5.com/en/articles

## Community / marketplace

- MQL5.community (home): https://www.mql5.com/
- Market (buy/sell applications): https://www.mql5.com/en/market
- Forum: https://www.mql5.com/en/forum
- Freelance (paid development jobs): https://www.mql5.com/en/job
- Become a seller on MQL5.com: https://www.mql5.com/en/articles/385

## Selected articles from this email

- How much can you earn in the community?: https://www.mql5.com/en/articles/4234
- How to earn in the Freelance: https://www.mql5.com/en/articles/1019
- How to sell your products on the Market: https://www.mql5.com/en/articles/999

## Notes for the Forex project

- These resources describe the **native MQL5 path** (write indicators/EAs in
  MQL5, run them inside the MT5 terminal via MetaEditor and Strategy Tester).
  This is a different architecture from the currently planned Python,
  read-only integration with the installed Windows MT5 terminal
  (`forex-m0-foundation-prompt.md`, milestones M1/M2/M3/M27).
- If native MQL5 EA/indicator development is later adopted (in full or in
  part, e.g. an MQL5 indicator feeding data to the Python side, or a
  minimal MQL5 EA for order execution called from Python), that is an
  architecture decision to make deliberately and record — not something
  this reference index implies on its own.
- The Strategy Tester (visual + genetic-algorithm optimization, distributed
  agents) is worth a closer look against the project's own planned
  deterministic backtesting/walk-forward milestone — it may be a faster
  path to the same evidence, or a complementary one.
