# M29 proof

M29 proves a bounded recovery workflow on the real `GOMarketsMU-Demo` EURUSD quote surface. The collector first obtains a fixed read-only tick, then its client process is deliberately interrupted before response processing. A fresh invocation recovers the same fixed read-only operation. The retained bundle binds both successful envelopes, the interruption result, request identity, source revision and configuration fingerprint.

The interruption is client-side only. It cannot submit, modify, or cancel an order: `m27_demo_tick` has no order surface. Repeating this idempotent collection request is safe, while restarting the permanent listener is deliberately out of scope because it may be authorised to trade under M20.
