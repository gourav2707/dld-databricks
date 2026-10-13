-- D2: file registry and load log
CREATE TABLE IF NOT EXISTS dld.meta.file_registry (
  file_id       BIGINT GENERATED ALWAYS AS IDENTITY,
  file_path     STRING,
  raw_table     STRING,
  file_format   STRING,
  part_no       INT,
  size_bytes    BIGINT,
  sha256        STRING,
  status        STRING,
  note          STRING,
  registered_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS dld.meta.load_log (
  run_id       STRING,
  file_id      BIGINT,
  file_path    STRING,
  target_table STRING,
  method       STRING,
  rows_loaded  BIGINT,
  status       STRING,
  message      STRING,
  loaded_at    TIMESTAMP
);