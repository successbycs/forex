"""Free official calendar adapters for the M10 MVP path."""
from __future__ import annotations
import json, os, re
from datetime import UTC, datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
FRED_RELEASE_ID = 10
FRED_URL = "https://api.stlouisfed.org/fred/release/dates"
ECB_URL = "https://www.ecb.europa.eu/press/calendars/statscal/html/index.en.html"
def fred_cpi_release_dates() -> list[dict]:
 key=os.environ.get('FRED_API_KEY','').strip()
 if not key: raise ValueError('FRED_API_KEY is required for M10')
 q=urlencode({'release_id':FRED_RELEASE_ID,'api_key':key,'file_type':'json','limit':20,'sort_order':'desc','include_release_dates_with_no_data':'true'})
 p=json.load(urlopen(FRED_URL+'?'+q,timeout=30))
 return [{'source_id':'fred-alfred-us-macro','event_id':f"fred-release-{FRED_RELEASE_ID}-{r['date']}",'event_name':'Consumer Price Index release','scheduled_date':r['date'],'time_precision':'DATE_ONLY','availability_note':'Published source date; not a FRED/ALFRED availability timestamp.'} for r in p['release_dates']]
def ecb_calendar_sample() -> list[dict]:
 html=urlopen(Request(ECB_URL,headers={'User-Agent':'forex-m10-calendar/1.0'}),timeout=30).read().decode('utf-8','replace')
 matches=re.findall(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})\s+CET.{0,500}?Dataset:\s*([A-Z0-9]+)',html,re.S)
 if not matches: raise ValueError('ECB calendar did not expose a schedule sample')
 return [{'source_id':'ecb-data-portal-euro-macro','event_id':f'ecb-{dataset}-{day}-{time}','event_name':f'ECB statistical release ({dataset})','scheduled_at_local':f'{day} {time} CET','time_precision':'CET_SCHEDULED_TIME'} for day,time,dataset in matches[:20]]
def capture_events() -> dict:
 return {'retrieved_at_utc':datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z'),'us_events':fred_cpi_release_dates(),'eur_events':ecb_calendar_sample()}
