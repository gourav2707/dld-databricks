-- D5: evidence table for the reconciliation against DLD's published residential sale index
CREATE TABLE IF NOT EXISTS dld.meta.reconcile_result (
  run_id STRING, segment STRING, months BIGINT, first_month DATE, last_month DATE,
  level_corr DOUBLE, change_corr DOUBLE, median_ratio DOUBLE, passed BOOLEAN, checked_at TIMESTAMP
);