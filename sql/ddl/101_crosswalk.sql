-- D3: bridges (rebuilt whole from data), area crosswalk for the daily file, fuzzy review queue
CREATE TABLE IF NOT EXISTS dld.core.name_area_bridge (
  name STRING, via STRING, area_id BIGINT, n_area_ids BIGINT, area_ids ARRAY<BIGINT>, n_rows BIGINT
);
CREATE TABLE IF NOT EXISTS dld.core.name_project_bridge (
  name STRING, project_id BIGINT, n_project_ids BIGINT, project_ids ARRAY<BIGINT>
);
CREATE TABLE IF NOT EXISTS dld.core.developer_name_bridge (
  name STRING, developer_id BIGINT, n_developer_ids BIGINT, developer_ids ARRAY<BIGINT>
);
CREATE TABLE IF NOT EXISTS dld.core.area_crosswalk (
  area_en STRING, project_en STRING, master_project_en STRING, n_rows BIGINT,
  area_id BIGINT, rung INT, rung_name STRING
);
CREATE TABLE IF NOT EXISTS dld.meta.crosswalk_review (
  name STRING, candidate STRING, candidate_area_id BIGINT, via STRING, score DOUBLE,
  status STRING, suggested_at TIMESTAMP
);