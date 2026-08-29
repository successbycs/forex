# M1 weekend historical-fixture readiness

Historical EUR/USD data may be used during the market closure only as a
`HISTORICAL_FIXTURE` for development and no-lookahead tests. It is not
real-time market data and cannot satisfy the Phase 3 fresh-tick, current-spread,
restart, or execution milestones. M1 itself requires a governed export of
closed historical bars from the authenticated Demo terminal; a fixture alone
does not close it.

Raw historical extraction, validation, persistence, and governed simulation
remain M6, M7, M13, and M16 work. This M1 readiness utility merely prevents a
future implementation from treating a fixture as real-time data or seeing bars
after its requested decision time.
