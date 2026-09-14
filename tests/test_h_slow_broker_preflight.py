import pytest
from forex.h_slow_broker_preflight import *
def record():return {"ok":True,"status":"PREFLIGHT_OK","captured_at_utc":"2026-09-13T00:00:00Z","account_label":"H1_demo","account_scope_sha256":"sha256:"+"a"*64,"server":"GOMarketsMU-Demo","currency":"AUD","symbol":"EURUSD","bid":1.1,"ask":1.1,"tick_time_msc":1789257600000,"broker_timestamp_offset_seconds":0,"tick_age_seconds":0,"open_positions":0,"symbol_specification":{"name":"EURUSD","point":.00001,"trade_tick_size":.00001,"trade_tick_value_loss":1.,"trade_contract_size":100000.,"volume_min":.01,"volume_max":1.,"volume_step":.01,"trade_stops_level":0,"trade_freeze_level":0}}
def test_exact_operation_shape_validates():assert validate_broker_preflight(record(),expected_broker_timestamp_offset_seconds=0)["instrument"]=="EUR/USD"
@pytest.mark.parametrize("k,v",[("login",1),("status","x"),("tick_age_seconds",16),("ask",1.0),("symbol","EUR/USD")])
def test_old_or_hostile_shapes_refuse(k,v):
 r=record();r[k]=v
 with pytest.raises(HSlowBrokerPreflightError):validate_broker_preflight(r,expected_broker_timestamp_offset_seconds=0)
@pytest.mark.parametrize("mutate",[lambda r:r.update(tick_age_seconds=1),lambda r:r.update(tick_time_msc=1789257580000),lambda r:r["symbol_specification"].update(volume_min=2),lambda r:r["symbol_specification"].update(volume_step=.02)])
def test_forged_tick_age_or_invalid_volume_lattice_refuses(mutate):
 r=record();mutate(r)
 with pytest.raises(HSlowBrokerPreflightError):validate_broker_preflight(r,expected_broker_timestamp_offset_seconds=0)
def test_recomputed_stale_age_and_offset_drift_refuse():
 r=record();r["tick_time_msc"]-=15000500;r["tick_age_seconds"]=15
 with pytest.raises(HSlowBrokerPreflightError):validate_broker_preflight(r,expected_broker_timestamp_offset_seconds=0)
 r=record();r["broker_timestamp_offset_seconds"]=86400;r["tick_time_msc"]+=86400000
 with pytest.raises(HSlowBrokerPreflightError):validate_broker_preflight(r,expected_broker_timestamp_offset_seconds=0)
