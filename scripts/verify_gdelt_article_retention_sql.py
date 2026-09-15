#!/usr/bin/env python3
"""Exercise the deployed GDELT V3 PostgreSQL schema inside a rollback only.

This is intentionally an integration check, not a migration installer.  It
requires the exact T480 PostgreSQL service to already have migration 025.  The
test inserts an article, a second URL for the same content, two receipts and a
source link, prints only counts, then rolls every row back.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB_ROOT = Path("/home/chris/projects/cs-ai-lab-infra")

SQL = r"""
\set ON_ERROR_STOP on
BEGIN;
DO $$ BEGIN
  IF to_regclass('forex.gdelt_article') IS NULL
     OR to_regclass('forex.gdelt_article_retrieval_attempt') IS NULL
     OR to_regclass('forex.gdelt_article_source') IS NULL THEN
    RAISE EXCEPTION 'M11 V3 article retention migration is not installed';
  END IF;
END $$;
INSERT INTO forex.source_registry (source_id,contract_version,owner,license,cost_model,api_version,endpoint_allowlist,rate_limit,retention_rule,historical_depth,revision_support,timezone_policy,outage_policy,approval_status,secrets_reference,provenance_note)
VALUES ('gdelt-v3-rollback-contract','forex.gdelt-context.v3','integration','test','none','v3','[]'::jsonb,'none','rollback-only','none','none','UTC-normalised','none','PENDING_QUALIFICATION','NONE','rollback-only')
ON CONFLICT (source_id) DO NOTHING;
INSERT INTO forex.raw_observation (observation_id,contract_version,source_id,source_revision,observed_at_utc,available_at_utc,retrieved_at_utc,timezone,payload_sha256,payload_path,redacted)
VALUES ('gdelt-v3-rollback-observation','forex.gdelt-context.v3','gdelt-v3-rollback-contract','rollback','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z','UTC','sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','rollback://gdelt',true)
ON CONFLICT (observation_id) DO NOTHING;
-- This is the exact persist-article/receipt sequence used by the fixed n8n
-- nodes: append an attempt, deduplicate content, map URL/source, then update
-- the *returned* attempt_id with all egress receipt metadata.
WITH input AS (
  SELECT 'RETAINED'::text result_status,
    'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'::text content_sha256,
    'https://publisher.example/first'::text canonical_url,
    'Rollback title'::text title, 'Rollback body'::text body,
    'text/html'::text content_type, NULL::text failure_reason, 200::integer http_status,
    '2026-01-01T00:00:00Z'::timestamptz retrieved_at_utc,
    '[{"source_observation_id":"gdelt-v3-rollback-observation","gdelt_document_id":"rollback-document","bucket_time_utc":"2026-01-01T00:00:00Z","source_tone":1.0}]'::jsonb sources
), attempts AS (
  INSERT INTO forex.gdelt_article_retrieval_attempt (canonical_url,retrieved_at_utc,result_status,failure_reason,http_status,content_sha256,content_type)
  SELECT canonical_url,retrieved_at_utc,result_status,failure_reason,http_status,content_sha256,content_type FROM input RETURNING attempt_id
), inserted AS (
  INSERT INTO forex.gdelt_article (content_sha256,title,body,retrieved_at_utc,content_type)
  SELECT content_sha256,title,body,retrieved_at_utc,content_type FROM input WHERE result_status='RETAINED'
  ON CONFLICT (content_sha256) DO NOTHING RETURNING content_sha256
), retained AS (
  SELECT content_sha256 FROM inserted UNION
  SELECT article.content_sha256 FROM forex.gdelt_article article,input WHERE input.result_status='RETAINED' AND article.content_sha256=input.content_sha256
), urls AS (
  INSERT INTO forex.gdelt_article_url (content_sha256,canonical_url,first_retrieved_at_utc,last_retrieved_at_utc)
  SELECT retained.content_sha256,input.canonical_url,input.retrieved_at_utc,input.retrieved_at_utc FROM retained,input
  ON CONFLICT (content_sha256,canonical_url) DO UPDATE SET last_retrieved_at_utc=EXCLUDED.last_retrieved_at_utc
), second_url AS (
  INSERT INTO forex.gdelt_article_url (content_sha256,canonical_url,first_retrieved_at_utc,last_retrieved_at_utc)
  VALUES ('sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','https://syndicate.example/second','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z') ON CONFLICT DO NOTHING
), failed_attempt AS (
  INSERT INTO forex.gdelt_article_retrieval_attempt (canonical_url,retrieved_at_utc,result_status,failure_reason,http_status,content_sha256,content_type)
  VALUES ('https://publisher.example/failure','2026-01-01T00:00:00Z','FAILED','HTTP_STATUS_REJECTED',404,NULL,NULL)
), links AS (
  SELECT retained.content_sha256,source.source_observation_id,source.gdelt_document_id,source.bucket_time_utc,source.source_tone
  FROM retained,input CROSS JOIN LATERAL jsonb_to_recordset(input.sources) AS source(source_observation_id text,gdelt_document_id text,bucket_time_utc timestamptz,source_tone numeric)
), source_link AS (
  INSERT INTO forex.gdelt_article_source (content_sha256,source_observation_id,gdelt_document_id,bucket_time_utc,source_tone)
  SELECT content_sha256,source_observation_id,gdelt_document_id,bucket_time_utc,source_tone FROM links
  ON CONFLICT DO NOTHING
), receipt AS (
  UPDATE forex.gdelt_article_retrieval_attempt SET
    final_url='https://publisher.example/final', redirect_chain='["https://publisher.example/first","https://publisher.example/final"]'::jsonb,
    pinned_ip='93.184.216.34', byte_count=123, payload_sha256='sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'
  WHERE attempt_id=(SELECT attempt_id FROM attempts) RETURNING attempt_id
)
SELECT json_build_object(
  'article_rows',(SELECT count(*) FROM forex.gdelt_article WHERE content_sha256='sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
  'url_rows',(SELECT count(*) FROM forex.gdelt_article_url WHERE content_sha256='sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
  'attempt_rows',(SELECT count(*) FROM forex.gdelt_article_retrieval_attempt WHERE canonical_url LIKE 'https://publisher.example/%'),
  'source_links',(SELECT count(*) FROM forex.gdelt_article_source WHERE content_sha256='sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'),
  'receipt_exact_attempt',(SELECT count(*) FROM receipt),
  'receipt_metadata',(SELECT count(*) FROM forex.gdelt_article_retrieval_attempt WHERE attempt_id=(SELECT attempt_id FROM attempts) AND final_url='https://publisher.example/final' AND redirect_chain='["https://publisher.example/first","https://publisher.example/final"]'::jsonb AND pinned_ip='93.184.216.34' AND byte_count=123 AND payload_sha256='sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc')
) AS gdelt_v3_rollback_result;
ROLLBACK;
"""


def run(lab_root: Path = LAB_ROOT) -> dict[str, object]:
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-U", "cs_ai_lab", "-d", "cs_ai_lab", "-At"],
        cwd=lab_root, input=SQL, text=True, capture_output=True, check=False,
    )
    if result.returncode:
        return {"ok": False, "stdout": result.stdout, "stderr": result.stderr}
    records = [line for line in result.stdout.splitlines() if line.startswith("{")]
    if len(records) != 1:
        return {"ok": False, "stdout": result.stdout, "stderr": "rollback result was not returned"}
    value = json.loads(records[0])
    expected = {"article_rows": 1, "url_rows": 2, "attempt_rows": 2, "source_links": 1,
                "receipt_exact_attempt": 1, "receipt_metadata": 1}
    return {"ok": value == expected, "result": value}


def main() -> int:
    result = run()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
