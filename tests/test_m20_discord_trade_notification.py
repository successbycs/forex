from t480 import m20_discord_trade_notification as discord


def payload():
    return {
        "server": "GOMarketsMU-Demo", "symbol": "EURUSD", "proposal_id": "proposal-1",
        "position_ticket": 123, "side": "BUY", "strategy": "compression_breakout",
        "opened_at_utc": "2026-09-04T01:00:00Z", "closed_at_utc": "2026-09-04T01:05:00Z",
        "entry_price": 1.16295, "exit_price": 1.1634, "lots": 0.01,
        "close_reason": "TAKE_PROFIT", "gross_pnl_aud": 0.12, "commission_aud": -0.01, "fee_aud": -0.02,
        "swap_aud": 0.0, "estimated_cost_aud": 0.08, "realized_pnl_aud": 0.11,
        "liquidity": {"currency": "AUD", "balance": 100001.11, "equity": 100001.11, "free_margin": 100001.11, "margin": 0.0, "floating_pnl": 0.0},
    }


def test_renders_close_result_costs_and_liquidity():
    message = discord.render_sale(payload())
    assert "Demo EURUSD sold — profit: +0.11 AUD" in message
    assert "commission -0.01" in message
    assert "fee -0.02" in message
    assert "free margin 100,001.11" in message
    assert "Demo-only, broker-reconciled" in message


def test_is_disabled_without_local_opt_in(monkeypatch):
    monkeypatch.delenv("FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED", raising=False)
    result = discord.notify_sale(payload())
    assert result == {"ok": True, "delivery": "DISABLED", "proposal_id": "proposal-1"}


def test_refuses_a_non_demo_payload():
    candidate = payload()
    candidate["server"] = "GOMarketsMU-Live"
    try:
        discord.validate_sale(candidate)
    except ValueError as error:
        assert "Demo EURUSD" in str(error)
    else:
        raise AssertionError("live sale notification payload was accepted")


def open_payload():
    return {
        "server": "GOMarketsMU-Demo", "symbol": "EURUSD", "proposal_id": "proposal-1",
        "position_ticket": 123, "side": "BUY", "strategy": "compression_breakout",
        "opened_at_utc": "2026-09-07T03:00:00Z", "entry_price": 1.16295,
        "stop_loss": 1.16245, "take_profit": 1.16395, "lots": 0.01,
    }


def test_renders_durable_protected_open_as_wave_one_resume_prompt():
    message = discord.render_open(open_payload())
    assert "Demo EURUSD opened — resume Wave 1" in message
    assert "BUY 0.01 lots" in message
    assert "SL 1.16245 | TP 1.16395" in message
    assert "durable OPENED record confirmed" in message


def test_open_notification_is_disabled_without_local_opt_in(monkeypatch):
    monkeypatch.delenv("FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED", raising=False)
    result = discord.notify_open(open_payload())
    assert result == {"ok": True, "delivery": "DISABLED", "proposal_id": "proposal-1"}


def test_open_notification_refuses_live_or_unprotected_payloads():
    candidate = open_payload()
    candidate["server"] = "GOMarketsMU-Live"
    try:
        discord.validate_open(candidate)
    except ValueError as error:
        assert "Demo EURUSD" in str(error)
    else:
        raise AssertionError("live open notification payload was accepted")
    candidate = open_payload()
    candidate["stop_loss"] = 0
    try:
        discord.validate_open(candidate)
    except ValueError as error:
        assert "stop_loss" in str(error)
    else:
        raise AssertionError("unprotected open notification payload was accepted")


def test_accepts_the_legacy_discordapp_webhook_endpoint(monkeypatch):
    legacy = "https://discordapp.com/api/webhooks/123/token"
    monkeypatch.setenv("FOREX_M20_DISCORD_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("FOREX_M20_DISCORD_WEBHOOK_URL", legacy)
    assert discord._webhook_url() == legacy
