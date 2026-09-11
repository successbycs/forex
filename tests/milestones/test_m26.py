from forex.execution_revalidation import drill_revalidation
def test_m26_revalidates_or_refuses_for_freshness_spread_market_and_approval():
 r=drill_revalidation()['results']; assert r['valid']['outcome']=='REVALIDATED_SIMULATION'; assert r['stale']['reasons']==['QUOTE_NOT_FRESH']; assert r['spread']['reasons']==['SPREAD_LIMIT']; assert r['market']['reasons']==['MARKET_STATE_CHANGED']; assert r['expired']['reasons']==['APPROVAL_EXPIRED']; assert all(x['order_submission']=='STRUCTURALLY_DISABLED' for x in r.values())
