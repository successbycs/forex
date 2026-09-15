from __future__ import annotations
import base64
import json
from dataclasses import dataclass
from forex.gdelt_publisher_egress import MAX_RESPONSE_BYTES, fetch_archive, fetch_candidate, sign_candidate_envelope

SIGNING_KEY = "s" * 32

def candidate(url="https://publisher.example/story"):
    value={"canonical_url":url,"sources":[{"source_observation_id":"gdelt-gkg-v2-x","gdelt_document_id":"x","bucket_time_utc":"2026-09-15T00:00:00Z","source_tone":1.0}]}
    return json.dumps({"candidate":value,"aggregate_sha256":"sha256:"+"a"*64,"bucket_time_utc":"2026-09-15T00:00:00Z","signature":sign_candidate_envelope(candidate=value,aggregate_sha256="sha256:"+"a"*64,bucket_time_utc="2026-09-15T00:00:00Z",signing_key=SIGNING_KEY)}).encode()

def public_resolver(host, port, **_kwargs):
    assert port == 443
    return [(2,1,6,"",("93.184.216.34",443))]

@dataclass
class Response:
    status: int
    headers: list[tuple[str,str]]
    body: bytes
    def getheaders(self): return self.headers
    def read(self, size=-1):
        value = self.body if size < 0 else self.body[:size]
        self.body = self.body[len(value):]
        return value

class Connection:
    def __init__(self, host, ip, timeout, response): self.host,self.ip,self.timeout,self.response=host,ip,timeout,response
    def request(self, method, target, headers): self.requested=(method,target,headers)
    def getresponse(self): return self.response
    def close(self): pass

def factory(response, captured):
    def build(host, ip, timeout):
        captured.append((host,ip,timeout)); return Connection(host,ip,timeout,response)
    return build

def test_fetch_pins_resolved_public_ip_and_returns_base64_only_on_safe_success():
    captured=[]
    result=fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=public_resolver,connection_factory=factory(Response(200,[("Content-Type","text/html")],b"<title>x</title>"),captured))
    assert result["status"] == "RETAINED"
    assert base64.b64decode(result["content_base64"]) == b"<title>x</title>"
    assert captured[0][0:2] == ("publisher.example","93.184.216.34")
    assert result["canonical_url"] == "https://publisher.example/story"
    assert result["redirect_chain"] == ["https://publisher.example/story"]
    assert result["pinned_ip"] == "93.184.216.34" and result["byte_count"] == 16
    assert result["payload_sha256"].startswith("sha256:")

def test_refuses_private_resolution_ip_literals_and_arbitrary_candidate_shape():
    private=lambda *_args,**_kwargs:[(2,1,6,"",("127.0.0.1",443))]
    assert fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=private)["reason"] == "REFUSED_NON_GLOBAL_DESTINATION"
    assert fetch_candidate(candidate("https://127.0.0.1/x"),candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_IP_LITERAL"
    assert fetch_candidate(b'{"url":"https://publisher.example"}',candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_CANDIDATE"
    assert fetch_candidate(candidate("https://publisher.example:bad/x"),candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_URL"
    assert fetch_candidate(candidate("https://api.gomarkets.example/x"),candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_HOST"


def test_bearer_only_caller_cannot_alter_or_forge_a_signed_candidate():
    envelope=json.loads(candidate().decode())
    envelope["candidate"]["canonical_url"]="https://attacker.example/"
    assert fetch_candidate(json.dumps(envelope).encode(),candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_SIGNATURE"
    envelope["signature"]="0"*64
    assert fetch_candidate(json.dumps(envelope).encode(),candidate_signing_key=SIGNING_KEY)["reason"] == "REFUSED_SIGNATURE"

def test_refuses_mixed_dns_answers_when_any_answer_is_not_public_unicast():
    mixed=lambda *_args,**_kwargs:[(2,1,6,"",("93.184.216.34",443)),(2,1,6,"",("224.0.0.1",443))]
    assert fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=mixed)["reason"] == "REFUSED_NON_GLOBAL_DESTINATION"

def test_redirect_is_consistently_refused_and_cap_and_status_are_refused_without_content():
    calls=[]; responses=iter([Response(302,[("Location","https://other.example/x")],b""),Response(200,[("Content-Type","text/html")],b"ok")])
    def build(host,ip,timeout):
        calls.append((host,ip)); return Connection(host,ip,timeout,next(responses))
    result=fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=public_resolver,connection_factory=build)
    assert result == {"status":"FAILED","reason":"REDIRECT_REFUSED","http_status":302}
    assert calls == [("publisher.example","93.184.216.34")]
    oversized=fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=public_resolver,connection_factory=factory(Response(200,[("Content-Type","text/html"),("Content-Length",str(MAX_RESPONSE_BYTES+1))],b""),[]))
    assert oversized == {"status":"FAILED","reason":"RESPONSE_TOO_LARGE","http_status":200}
    missing=fetch_candidate(candidate(),candidate_signing_key=SIGNING_KEY,resolver=public_resolver,connection_factory=factory(Response(404,[("Content-Type","text/html")],b""),[]))
    assert missing == {"status":"FAILED","reason":"HTTP_STATUS_REJECTED","http_status":404}


def test_archive_route_is_a_fixed_gdelt_only_exit_and_returns_zip_bytes():
    raw = json.dumps({"url": "https://data.gdeltproject.org/gdeltv2/20260915000000.gkg.csv.zip"}).encode()
    result, data = fetch_archive(raw, resolver=public_resolver,
                                 connection_factory=factory(Response(200, [("Content-Type", "application/zip")], b"PKzip"), []))
    assert result["status"] == "OK" and data == b"PKzip"
    bad, no_data = fetch_archive(json.dumps({"url": "https://publisher.example/a"}).encode())
    assert bad["reason"] == "REFUSED_ARCHIVE" and no_data is None
