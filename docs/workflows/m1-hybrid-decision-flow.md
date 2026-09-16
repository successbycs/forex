# M1 hybrid decision flow

This diagram is the proposed target shape for the EUR/USD M1 Demo workflow.
It combines the current repository's decision provenance, fixed Demo execution,
and reconciliation controls with a candle-keyed decision cadence and qualified
event-risk handling. It is not a claim of profitability and does not itself
change the running listener.

```mermaid
flowchart TD
    A[New completed EUR/USD M1 candle] --> B[Obtain fresh executable quote<br/>and create one candle-keyed snapshot]
    B --> C{M1 data complete, fresh,<br/>and point-in-time valid?}
    C -- No --> NT[NO_TRADE<br/>record exact reason]
    C -- Yes --> D{Demo account, broker, lease,<br/>hold, position and recovery state safe?}
    D -- No --> NT
    D -- Yes --> E{Qualified event-risk context available?}
    E -- Unavailable when event gate enabled --> NT
    E -- Active event window --> NT
    E -- Clear or annotation-only policy --> F{Spread, financing, session,<br/>and execution conditions acceptable?}
    F -- No --> NT
    F -- Yes --> G[Evaluate five M1 strategies<br/>on the same immutable snapshot]
    G --> H{At most one executable<br/>strategy owner selected?}
    H -- No --> NT
    H -- Yes --> I[Calculate entry, protective stop,<br/>target, capped size and expected costs]
    I --> J{Risk, exposure, drawdown,<br/>cost and duplicate-order gates pass?}
    J -- No --> NT
    J -- Yes --> K[Persist proposal and<br/>idempotency reservation]
    K --> L[Submit one protected<br/>GOMarketsMU-Demo order]
    L --> M[Monitor position, apply required exit,<br/>and reconcile broker history]
    NT --> N[Journal snapshot, gates, strategy results,<br/>reason code and outcome]
    M --> N

    S[Completed M5/H1 bars] -. shadow context only .-> T[Record context, alignment<br/>and point-in-time availability]
    T -. does not change M1 authority today .-> N

    classDef active fill:#d9ead3,stroke:#38761d,color:#000;
    classDef decision fill:#cfe2f3,stroke:#1155cc,color:#000;
    classDef safe fill:#fce5cd,stroke:#b45f06,color:#000;
    classDef shadow fill:#ead1dc,stroke:#a64d79,color:#000,stroke-dasharray: 5 5;
    class A,B,G,I,K,L,M,N active;
    class C,D,E,F,H,J decision;
    class NT safe;
    class S,T shadow;
```

## Status key

- Green: current implementation direction; individual gates may still have
  documented limitations.
- Blue: decision points that must return an explicit reason when refusing.
- Orange: normal safe refusal outcome.
- Purple dashed: currently shadow-only context. M5/H1 cannot create, veto, or
  own an M1 trade until separately authorised and tested.

The event decision is conditional by design. The current shipped event policy
is annotation-only; therefore it must not be represented as an active entry
veto until a qualified point-in-time event context is deployed. If it is
enabled later, unavailable or invalid required context must refuse a new entry.

See [M1 Demo decision workflow](m1-demo-decision-workflow.md) for current
behaviour and [M1 decision-workflow end-state review](../reviews/m1-decision-workflow-end-state.md)
for the target capability, gaps, and promotion criteria.
