"""Local-only two-document exact-time derivation for FOMC/ECB policy events."""
from __future__ import annotations
import hashlib,json,re
from datetime import datetime,UTC
from zoneinfo import ZoneInfo
from typing import Any
from forex.first_party_policy_capture import SOURCES,PolicyCaptureError

TIMING_URLS={"FOMC_POLICY_DECISION":"https://www.federalreserve.gov/newsevents/pressreleases/monetary20240809a.htm","ECB_POLICY_DECISION":"https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html"}
class PolicyTimingError(ValueError):pass
def _sha(x):return 'sha256:'+hashlib.sha256(x).hexdigest()
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def timing_bundle_sha256(bundle:dict[str,Any])->str:
 """Return the digest for the immutable fields of a timing derivation."""
 if not isinstance(bundle,dict):raise PolicyTimingError('policy timing bundle is invalid')
 payload={key:value for key,value in bundle.items() if key!='bundle_sha256'}
 return _sha(_canonical(payload))
def _text(raw):
 if not isinstance(raw,bytes) or not raw:raise PolicyTimingError('retained document is invalid')
 try:return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',raw.decode('utf-8')))
 except UnicodeDecodeError as e:raise PolicyTimingError('retained document is not UTF-8') from e
def _clock(local,zone):
 dt=datetime.fromisoformat(local);z=ZoneInfo(zone);xs=[]
 for fold in (0,1):
  a=dt.replace(tzinfo=z,fold=fold)
  if a.astimezone(UTC).astimezone(z).replace(tzinfo=None)==dt:xs.append(a.astimezone(UTC))
 if len({x.isoformat() for x in xs})!=1:raise PolicyTimingError('policy local clock is ambiguous or nonexistent')
 return xs[0].isoformat().replace('+00:00','Z')
def derive_exact_policy_time(*,family_id:str,target_date:str,calendar_raw:bytes,calendar_url:str,timing_raw:bytes,timing_url:str)->dict[str,Any]:
 if family_id not in SOURCES or calendar_url!=SOURCES[family_id][1] or timing_url!=TIMING_URLS.get(family_id):raise PolicyTimingError('policy source URL is not allowlisted')
 cal,timing=_text(calendar_raw),_text(timing_raw)
 months='January|February|March|April|May|June|July|August|September|October|November|December'
 if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',target_date):raise PolicyTimingError('target policy date is invalid')
 if family_id=='FOMC_POLICY_DECISION':
  matches=[]
  year=target_date[:4]
  section=re.search(r'\b'+year+r'\s+FOMC\s+Meetings\b(.*?)(?=\b20\d{2}\s+FOMC\s+Meetings\b|\Z)',cal,re.I)
  if section:
   for m in re.finditer(r'('+months+r')\s+(\d{1,2})\s*[-–]\s*(\d{1,2})',section.group(1),re.I):
    date=f'{year}-{datetime.strptime(m.group(1),"%B").month:02d}-{int(m.group(3)):02d}'
    if date==target_date:matches.append(m)
  ok=re.search(r'policy statement.{0,100}2(?::00)?\s*p\.m\.?.{0,80}Eastern',timing,re.I);zone='America/New_York'
  if len(matches)!=1 or not ok:raise PolicyTimingError('FOMC target meeting or official timing declaration is absent or ambiguous')
  local=target_date+'T14:00'
 else:
  pattern=r'Day\s*2\s*[:\-]?\s*(\d{1,2})\s+('+months+r')\s+(20\d{2}).{0,160}\bmonetary policy\b'
  # A current ECB page has one date-first entry per row.  Do not let a
  # preceding row consume a later row's policy/Day-2 marker.
  next_date=r'\b\d{1,2}/\d{1,2}/20\d{2}\b'
  entry=r'(?:(?!'+next_date+r').)'
  date_first=r'(\d{1,2})/(\d{1,2})/(20\d{2})'+entry+r'{0,800}?\bmonetary policy\b'+entry+r'{0,400}?\(\s*Day\s*2\s*\)'
  matches=[m for m in re.finditer(pattern,cal,re.I) if f'{m.group(3)}-{datetime.strptime(m.group(2),"%B").month:02d}-{int(m.group(1)):02d}'==target_date]
  matches += [m for m in re.finditer(date_first,cal,re.I) if f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'==target_date]
  ok=re.search(r'(?:decisions.{0,80}published|published.{0,80}decisions).{0,100}14:15\s*CET',timing,re.I);zone='Europe/Berlin'
  if len(matches)!=1 or not ok:raise PolicyTimingError('ECB Day 2 policy meeting or official timing declaration is absent or ambiguous')
  local=target_date+'T14:15'
 result={'schema_version':'forex.first-party-policy-timing-bundle.v1','family_id':family_id,'target_date':target_date,'calendar_url':calendar_url,'calendar_sha256':_sha(calendar_raw),'timing_url':timing_url,'timing_sha256':_sha(timing_raw),'timing_source_limitation':'Publisher timing declaration is source-version-specific; retain its exact bytes and URL.','scheduled_at_local':local,'timezone':zone,'scheduled_at_utc':_clock(local,zone),'execution_authority':False,'coverage_status':'UNKNOWN'}
 return {**result,'bundle_sha256':timing_bundle_sha256(result)}
