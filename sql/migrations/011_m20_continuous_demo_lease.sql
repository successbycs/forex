-- M20 remediation: Demo-only authority is continuous at the operator's
-- direction.  Server, instrument, trade, notional, position, loss, and audit
-- constraints remain unchanged.
BEGIN;

ALTER TABLE forex.demo_trade_session
    DROP CONSTRAINT IF EXISTS demo_trade_session_check;

ALTER TABLE forex.demo_trade_session
    DROP CONSTRAINT IF EXISTS demo_trade_session_check1;

COMMIT;
