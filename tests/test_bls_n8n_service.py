from __future__ import annotations

import base64
import http.client
import json
import threading
from pathlib import Path

from forex.bls_n8n_service import BLSN8nServiceConfig, BLSN8nServiceConfigError, create_server
from forex.bls_n8n_projection import project_verified_n8n_bls_store
from tests.test_bls_monthly_capture import RAW


def handoff() -> bytes:
    return json.dumps({"capture_id":"service-1","year":2026,"month":9,
        "started_at_utc":"2026-09-14T00:00:00Z","completed_at_utc":"2026-09-14T00:00:01Z",
        "status_code":200,"content_type":"text/html","body_base64":base64.b64encode(b"<html>x</html>").decode(),
        "body_complete":True}, separators=(",", ":")).encode()


def config(tmp_path: Path) -> BLSN8nServiceConfig:
    return BLSN8nServiceConfig("127.0.0.1", 0, tmp_path / "store", "a" * 32, "fixed", "sha256:" + "a" * 64)


def request(server, body=handoff(), token="a" * 32):
    port = server.server_address[1]
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    connection.request("POST", "/forex/a1/retain-bls", body=body,
                       headers={"Content-Type":"application/json", "Authorization":"Bearer " + token})
    response = connection.getresponse(); value = json.loads(response.read()); connection.close()
    return response.status, value


def test_http_service_requires_authentication_and_retains_idempotently(tmp_path):
    server = create_server(config(tmp_path)); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        assert request(server, token="wrong")[0] == 401
        first = request(server); second = request(server)
        assert first == second and first[0] == 200 and first[1]["status"] == "RETAINED"
        assert (tmp_path / "store" / "n8n-receipts" / "service-1").is_dir()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_http_service_refuses_duplicate_json_fields_before_store_write(tmp_path):
    server = create_server(config(tmp_path)); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        status, value = request(server, b'{"capture_id":"a","capture_id":"b"}')
        assert (status, value["status"]) == (400, "REFUSED_HANDOFF")
        assert not (tmp_path / "store").exists()
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_http_service_round_trips_real_monthly_html_to_verified_projection(tmp_path):
    value = json.loads(handoff())
    value["capture_id"] = "service-real"
    value["body_base64"] = base64.b64encode(RAW).decode()
    server = create_server(config(tmp_path)); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        first = request(server, json.dumps(value, separators=(",", ":")).encode())
        second = request(server, json.dumps(value, separators=(",", ":")).encode())
        assert first == second and first[0] == 200
        projection = project_verified_n8n_bls_store(tmp_path / "store", expected_workflow_id="fixed", expected_workflow_sha256="sha256:" + "a" * 64)
        assert projection["facts"]
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_http_service_refuses_transfer_encoding_framing(tmp_path):
    server = create_server(config(tmp_path)); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=2)
        connection.request("POST", "/forex/a1/retain-bls", body=handoff(), headers={"Content-Type":"application/json", "Authorization":"Bearer " + "a" * 32, "Transfer-Encoding":"chunked"})
        response = connection.getresponse(); value = json.loads(response.read()); connection.close()
        assert (response.status, value["status"]) == (400, "REFUSED_FRAMING")
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def test_environment_config_is_complete_and_loopback_only(tmp_path):
    base = {"FOREX_BLS_N8N_BIND_HOST":"127.0.0.1", "FOREX_BLS_N8N_PORT":"8091",
            "FOREX_BLS_N8N_STORE":str(tmp_path / "store"), "FOREX_BLS_N8N_HANDOFF_TOKEN":"a" * 32,
            "FOREX_BLS_N8N_WORKFLOW_ID":"fixed", "FOREX_BLS_N8N_WORKFLOW_SHA256":"sha256:" + "a" * 64}
    assert BLSN8nServiceConfig.from_environ(base).port == 8091
    base["FOREX_BLS_N8N_BIND_HOST"] = "0.0.0.0"
    try:
        BLSN8nServiceConfig.from_environ(base)
    except BLSN8nServiceConfigError:
        pass
    else:
        raise AssertionError("non-loopback bind was accepted")
