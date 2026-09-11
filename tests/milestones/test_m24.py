from pathlib import Path
from forex.simulated_intents import drill_intents

def test_m24_produces_buy_sell_and_refused_no_trade_records_with_a_cutoff():
 r={x['intent_id']:x for x in drill_intents(Path(__file__).resolve().parents[2])['results']}
 assert r['buy']['action']=='BUY' and r['sell']['action']=='SELL'
 assert r['no-trade']['action']=='NO_TRADE' and 'NO_DIRECTIONAL_INTENT' in r['no-trade']['refusal_reasons']
 assert r['risk-refused']['action']=='NO_TRADE' and {'RISK_REFUSED','SIZING_REFUSED'} <= set(r['risk-refused']['refusal_reasons'])
 assert all(x['mandatory_exit_cutoff_utc'].endswith('18:00:00Z') and x['order_submission']=='STRUCTURALLY_DISABLED' for x in r.values())
