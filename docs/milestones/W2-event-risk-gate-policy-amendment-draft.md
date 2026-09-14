# Draft — W2 M1 event-risk gate policy amendment

Status: planning only. This draft does not amend any governed execution
configuration, enable the prepared evaluator, alter the M20 policy kernel,
listener, order route, or a Demo trade.

The shipped `config/m1_event_risk_gate.json` is deliberately disabled. Its
only supported future scope is **new EUR/USD entries**; it must not close,
amend, or manage an existing position. When enabled, missing, partial or
ambiguous primary-source context must refuse a new entry. A qualified event in
the configured pre/post window must also refuse a new entry. It is not a
directional signal.

Before a separate amendment can activate it, the owner must approve a bounded
policy change that binds: the gate configuration digest; first-party BLS,
FOMC and ECB source contracts; retained-capture/parser coverage; a decision-
time provenance report; the M1 sidecar digest; and the exact listener/kernel
revision. The integration must demonstrate that disabled mode leaves the
existing M1 decision and execution output byte-for-byte unchanged, and that
enabled mode fails closed for unavailable, partial, ambiguous and tampered
context. It also needs fresh Demo observation and normal independent review.

No such amendment, activation, proof, or review is supplied by this draft.
