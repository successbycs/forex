-- M20 projected-cost components.  This extends only new audit metadata;
-- existing immutable selection rows remain historically unchanged.

BEGIN;

ALTER TABLE forex.demo_strategy_selection
    ADD COLUMN IF NOT EXISTS entry_spread_cost_aud NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS expected_exit_spread_cost_aud NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS commission_allowance_aud NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS slippage_allowance_aud NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS expected_swap_aud NUMERIC(14,2),
    ADD COLUMN IF NOT EXISTS projected_gross_profit_at_take_profit_aud NUMERIC(14,2);

ALTER TABLE forex.demo_strategy_selection
    ADD CONSTRAINT demo_strategy_selection_projected_cost_components_check
    CHECK (
        (cost_coverage_status = 'NOT_APPLICABLE') = (
            entry_spread_cost_aud IS NULL
            AND expected_exit_spread_cost_aud IS NULL
            AND commission_allowance_aud IS NULL
            AND slippage_allowance_aud IS NULL
            AND expected_swap_aud IS NULL
            AND projected_gross_profit_at_take_profit_aud IS NULL
        )
    ),
    ADD CONSTRAINT demo_strategy_selection_projected_cost_components_nonnegative_check
    CHECK (
        entry_spread_cost_aud IS NULL OR (
            entry_spread_cost_aud >= 0 AND expected_exit_spread_cost_aud >= 0
            AND commission_allowance_aud >= 0 AND slippage_allowance_aud >= 0
            AND expected_swap_aud >= 0 AND projected_gross_profit_at_take_profit_aud >= 0
        )
    );

COMMIT;
