from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gdelt_article_sql", ROOT / "scripts" / "verify_gdelt_article_retention_sql.py")
assert SPEC and SPEC.loader
integration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(integration)


def test_rollback_integration_is_exact_postgresql_coverage_and_never_commits():
    sql = integration.SQL
    assert "BEGIN;" in sql and "ROLLBACK;" in sql and "COMMIT;" not in sql
    assert "forex.gdelt_article" in sql
    assert "forex.gdelt_article_url" in sql
    assert "forex.gdelt_article_retrieval_attempt" in sql
    assert "forex.gdelt_article_source" in sql
    assert "article_rows" in sql and "url_rows" in sql and "attempt_rows" in sql
    assert "WHERE attempt_id=(SELECT attempt_id FROM attempts)" in sql
    assert "redirect_chain" in sql and "pinned_ip" in sql and "payload_sha256" in sql


def test_rollback_result_requires_one_content_record_and_two_deduplicated_urls(monkeypatch, tmp_path):
    class Result:
        returncode = 0
        stdout = '{"article_rows" : 1, "url_rows" : 2, "attempt_rows" : 2, "source_links" : 1, "receipt_exact_attempt" : 1, "receipt_metadata" : 1}\n'
        stderr = ""
    monkeypatch.setattr(integration.subprocess, "run", lambda *args, **kwargs: Result())
    assert integration.run(tmp_path) == {"ok": True, "result": {"article_rows": 1, "url_rows": 2, "attempt_rows": 2, "source_links": 1, "receipt_exact_attempt": 1, "receipt_metadata": 1}}
