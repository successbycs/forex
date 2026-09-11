from pathlib import Path
from forex.simulated_sizing import drill_sizing

def test_m23_sizes_only_an_m22_approved_simulation_within_loss_budget():
    results={item['intent_id']:item for item in drill_sizing(Path(__file__).resolve().parents[2])['results']}
    assert results['sized']['outcome']=='SIZE_SIMULATION'
    assert results['sized']['volume_lots']==0.1 and results['sized']['planned_loss_aud']==100.0
    assert results['risk-refused']['reason']=='RISK_NOT_APPROVED'
    assert results['too-small']['reason']=='MINIMUM_VOLUME_EXCEEDS_RISK_BUDGET'
    assert all(item['order_submission']=='STRUCTURALLY_DISABLED' for item in results.values())
