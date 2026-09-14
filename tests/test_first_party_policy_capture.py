import pytest
from forex.first_party_policy_capture import PolicyCaptureError,SOURCES,parse_retained_policy_html,retain_policy_capture

def parse(family, html):
 return parse_retained_policy_html(html.encode(),family_id=family,source_url=SOURCES[family][1],capture_completed_at_utc='2026-09-13T00:00:00Z')
def test_actual_fomc_date_pattern_is_retained_as_date_only_not_exact():
 r=parse('FOMC_POLICY_DECISION','<h2>2026 FOMC Meetings</h2><p>January 27-28</p>')
 assert r['records']==[] and r['quarantined'][0]['reason']=='FOMC_MEETING_DATE_ONLY_STATEMENT_TIME_UNDECLARED' and r['coverage_status']=='UNKNOWN'
def test_actual_ecb_day_pattern_is_retained_as_date_only_not_exact():
 r=parse('ECB_POLICY_DECISION','<p>29-30 October 2026 Governing Council monetary policy meeting</p>')
 assert r['records']==[] and r['quarantined'][0]['reason']=='ECB_POLICY_MEETING_DATE_ONLY_DECISION_TIME_UNDECLARED'
@pytest.mark.parametrize('family,html',[('FOMC_POLICY_DECISION','<html>calendar unavailable</html>'),('ECB_POLICY_DECISION','<p>29 October 2026 meeting</p>')])
def test_missing_or_malformed_official_pattern_refuses_exact_record(family,html):
 r=parse(family,html);assert r['records']==[] and r['quarantined'][0]['reason']=='OFFICIAL_POLICY_CALENDAR_PATTERN_NOT_FOUND'
def test_source_binding_and_local_retention_are_fail_closed(tmp_path):
 family='FOMC_POLICY_DECISION'; raw=b'<p>January 27-28 2026</p>'
 with pytest.raises(PolicyCaptureError):parse_retained_policy_html(raw,family_id=family,source_url='https://bad',capture_completed_at_utc='2026-09-13T00:00:00Z')
 x=retain_policy_capture(tmp_path,capture_id='one',raw=raw,family_id=family,source_url=SOURCES[family][1],capture_completed_at_utc='2026-09-13T00:00:00Z');assert (tmp_path/'one/raw.html').is_file() and x['parser_result']['records']==[]
 with pytest.raises(PolicyCaptureError):retain_policy_capture(tmp_path,capture_id='one',raw=raw,family_id=family,source_url=SOURCES[family][1],capture_completed_at_utc='2026-09-13T00:00:00Z')
def test_symlinked_capture_root_ancestor_is_refused(tmp_path):
 actual=tmp_path/'actual';actual.mkdir();link=tmp_path/'link';link.symlink_to(actual,target_is_directory=True)
 with pytest.raises(PolicyCaptureError,match='unsafe'):
  retain_policy_capture(link/'nested',capture_id='one',raw=b'<p>January 27-28 2026</p>',family_id='FOMC_POLICY_DECISION',source_url=SOURCES['FOMC_POLICY_DECISION'][1],capture_completed_at_utc='2026-09-13T00:00:00Z')
