# M15 explainable ML baseline model card

`eurusd-linear-baseline.v1` is a small deterministic offline centroid
classifier, not a production model. It trains on closed EUR/USD H1 bars only:
each two-bar-return / three-bar-range feature window is labelled using the
following closed bar's direction. It retains the BUY and SELL feature
centroids and selects the nearer class for the current window. Its bounded
0–100 advisory score maps to `BUY`, `SELL`, or `NO_TRADE`; an event blackout
always produces `NO_TRADE`.

The output is research-only. It cannot place, approve, suggest sizing for, or
otherwise execute an order. It establishes neither predictive performance nor
a trading edge.
