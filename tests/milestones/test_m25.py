from forex.human_approval import drill_approvals
def test_m25_scoped_expiring_human_approval_fails_closed():
 r=drill_approvals()['results']; assert r['accepted']['outcome']=='APPROVED_FOR_FUTURE_REVALIDATION_ONLY'; assert r['rejected']['reason']=='HUMAN_REJECTED'; assert r['expired']['reason']=='APPROVAL_EXPIRED'; assert r['mismatch']['reason']=='INTENT_MISMATCH'; assert all(x['order_submission']=='STRUCTURALLY_DISABLED' for x in r.values())
