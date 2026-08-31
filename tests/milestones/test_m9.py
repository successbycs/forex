from forex.ecb_macro import EcbMacroError, normalise_csv, sample_url
import pytest


CSV = b'KEY,TIME_PERIOD,OBS_VALUE,OBS_STATUS,TITLE\nICP.M.U2.N.000000.4.ANR,2024-01,2.8,A,HICP - Overall index\n'


def test_m9_uses_fixed_ecb_series_with_history_requested():
    url = sample_url()
    assert 'ICP/M.U2.N.000000.4.ANR' in url and 'includeHistory=true' in url


def test_m9_retains_metadata_utc_retrieval_and_raw_hash():
    result = normalise_csv(CSV, '2026-08-31T00:00:00Z')
    assert result['include_history'] is True and result['observations'][0]['value'] == 2.8
    with pytest.raises(EcbMacroError, match='UTC'):
        normalise_csv(CSV, '2026-08-31T00:00:00+00:00')
