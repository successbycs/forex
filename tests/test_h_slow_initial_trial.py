from pathlib import Path
import pytest
from forex.h_slow_initial_trial import *
ROOT=Path(__file__).parents[1]
def test_fixed_demo_trial_is_submission_disabled():
 r=load_initial_trial(ROOT/"config/h_slow_initial_trial.json");assert r["submission_status"]=="DISABLED_NOT_ROUTED" and r["execution_authority"] is False
def test_dynamic_or_credential_like_fields_refuse():
 r=load_initial_trial(ROOT/"config/h_slow_initial_trial.json");r["balance"]=1
 with pytest.raises(HSlowInitialTrialError):validate_initial_trial(r)

@pytest.mark.parametrize(("field","value"),[("max_open_positions",True),("max_open_positions",1.0),("maximum_volume_lots",1),("max_loss_aud",1000.1)])
def test_initial_trial_cannot_expand_canonical_fixed_h1_ceilings(field,value):
 r=load_initial_trial(ROOT/"config/h_slow_initial_trial.json");r[field]=value
 with pytest.raises(HSlowInitialTrialError):validate_initial_trial(r)
