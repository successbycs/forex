import pytest
from forex.first_party_policy_timing import derive_exact_policy_time,PolicyTimingError,TIMING_URLS
from forex.first_party_policy_capture import SOURCES
def derive(f,d,c,t):return derive_exact_policy_time(family_id=f,target_date=d,calendar_raw=c.encode(),calendar_url=SOURCES[f][1],timing_raw=t.encode(),timing_url=TIMING_URLS[f])
def test_fomc_two_documents_derive_second_day_eastern_time():
 r=derive('FOMC_POLICY_DECISION','2026-01-28','#### 2025 FOMC Meetings January 28-29 #### 2026 FOMC Meetings January 27-28 March 17-18 #### 2027 FOMC Meetings January 26-27','The policy statement will be released at 2:00 p.m. Eastern Time.');assert r['scheduled_at_local']=='2026-01-28T14:00' and r['execution_authority'] is False
def test_actual_fed_and_ecb_timing_wording_is_accepted_only_at_declared_times():
 f=derive('FOMC_POLICY_DECISION','2026-01-28','#### 2026 FOMC Meetings January 27-28','The Committee releases a policy statement at 2 p.m. Eastern Time after each regularly scheduled meeting.')
 e=derive('ECB_POLICY_DECISION','2026-10-30','Day 2: 30 October 2026 Governing Council monetary policy meeting',"The ECB's monetary policy decisions are published in a press release at 14:15 CET.")
 assert f['scheduled_at_local'].endswith('14:00') and e['scheduled_at_local'].endswith('14:15')
def test_ecb_two_documents_derive_policy_day_cet_time():
 r=derive('ECB_POLICY_DECISION','2026-10-30','Day 1: 29 October 2026 Governing Council meeting Day 2: 30 October 2026 Governing Council monetary policy meeting','Monetary policy decisions are published at 14:15 CET.');assert r['scheduled_at_local']=='2026-10-30T14:15'
def test_ecb_actual_date_first_day2_calendar_form_is_accepted():
 r=derive('ECB_POLICY_DECISION','2026-10-29','29/10/2026 Governing Council monetary policy meeting and press conference (Day 2)','The ECB monetary policy decisions are published in a press release at 14:15 CET.')
 assert r['scheduled_at_local']=='2026-10-29T14:15'
def test_ecb_date_first_entry_is_bounded_at_next_calendar_date():
 calendar=('27/10/2026 Governing Council general meeting (Day 1) '
           '28/10/2026 Governing Council monetary policy meeting (Day 1) '
           '29/10/2026 Governing Council monetary policy meeting and press conference (Day 2)')
 r=derive('ECB_POLICY_DECISION','2026-10-29',calendar,'decisions published at 14:15 CET')
 assert r['scheduled_at_local']=='2026-10-29T14:15'
@pytest.mark.parametrize('calendar',["29/10/2026 Governing Council monetary policy meeting (Day 1)","29/10/2026 Governing Council general meeting (Day 2)"])
def test_ecb_date_first_day1_or_non_policy_entry_refuses(calendar):
 with pytest.raises(PolicyTimingError):derive('ECB_POLICY_DECISION','2026-10-29',calendar,'decisions published at 14:15 CET')
@pytest.mark.parametrize('c,t',[('January 27-28, 2026','no time'),('no date','policy statement 2:00 p.m. Eastern')])
def test_missing_either_document_refuses(c,t):
 with pytest.raises(PolicyTimingError):derive('FOMC_POLICY_DECISION','2026-01-28',c,t)
def test_wrong_source_url_refuses():
 with pytest.raises(PolicyTimingError):derive_exact_policy_time(family_id='FOMC_POLICY_DECISION',target_date='2026-01-28',calendar_raw=b'January 27-28, 2026',calendar_url='https://bad',timing_raw=b'policy statement 2:00 p.m. Eastern',timing_url=TIMING_URLS['FOMC_POLICY_DECISION'])
def test_ecb_day1_only_and_wrong_fomc_target_refuse():
 with pytest.raises(PolicyTimingError):derive('ECB_POLICY_DECISION','2026-10-29','Day 1: 29 October 2026 Governing Council monetary policy meeting','decisions published 14:15 CET')
 with pytest.raises(PolicyTimingError):derive('FOMC_POLICY_DECISION','2026-03-18','#### 2026 FOMC Meetings January 27-28','policy statement 2:00 p.m. Eastern')
