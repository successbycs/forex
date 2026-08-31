"""Bounded GDELT aggregate-tone prototype; never a trading signal."""
from __future__ import annotations
import json
from datetime import UTC,datetime
from urllib.parse import urlencode
from urllib.request import urlopen
URL='https://api.gdeltproject.org/api/v2/doc/doc'
def fetch() -> dict:
 q=urlencode({'query':'(EUR OR euro) (USD OR dollar)','mode':'TimelineTone','format':'json','maxrecords':'20'})
 raw=urlopen(URL+'?'+q,timeout=30).read(); p=json.loads(raw)
 return {'source_id':'gdelt-sentiment-prototype','query_definition':'(EUR OR euro) (USD OR dollar)','retrieved_at_utc':datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z'),'raw_sha256':__import__('hashlib').sha256(raw).hexdigest(),'uncertainty':'EXPERIMENTAL_CONTEXT_ONLY','timeline':p.get('timeline',[])}
