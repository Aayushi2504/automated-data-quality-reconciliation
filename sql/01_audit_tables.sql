-- Audit tables written by dq_framework.reporting.persist (pandas creates them
-- automatically; this DDL is the production-grade equivalent, e.g. for Snowflake/Postgres).

CREATE TABLE IF NOT EXISTS dq_results (
  run_id       VARCHAR(32),
  run_ts       TIMESTAMP,
  dataset      VARCHAR(100),
  "check"      VARCHAR(100),
  "column"     VARCHAR(100),
  severity     VARCHAR(10),
  failed_rows  INTEGER,
  detail       VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS dq_exceptions (
  run_id       VARCHAR(32),
  run_ts       TIMESTAMP,
  dataset      VARCHAR(100),
  "check"      VARCHAR(100),
  "column"     VARCHAR(100),
  severity     VARCHAR(10),
  record_key   VARCHAR(200),
  value        VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS dq_run_summary (
  run_id VARCHAR(32), run_ts TIMESTAMP, status VARCHAR(25),
  checks_run INTEGER, checks_failed INTEGER, errors INTEGER, warnings INTEGER, records_flagged INTEGER
);
