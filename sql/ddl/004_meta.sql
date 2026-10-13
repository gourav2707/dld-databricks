-- D1: table where checks/run_all.py writes its evidence
CREATE TABLE IF NOT EXISTS dld.meta.check_result (
  run_id     STRING,
  check_name STRING,
  passed     BOOLEAN,
  detail     STRING,
  checked_at TIMESTAMP
);