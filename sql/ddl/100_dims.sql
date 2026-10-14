-- D3: dimensions. Keys are DLD's own ids. -1 = Unknown (empty in source), -2 = Not matched.
CREATE TABLE IF NOT EXISTS dld.core.dim_area (
  area_id BIGINT, area_name_en STRING, area_name_ar STRING, municipality_number STRING, source STRING
);
CREATE TABLE IF NOT EXISTS dld.core.dim_developer (
  developer_id BIGINT, developer_number STRING, developer_name_en STRING, developer_name_ar STRING,
  license_number STRING, legal_status_en STRING, registration_date STRING, source STRING
);
CREATE TABLE IF NOT EXISTS dld.core.dim_project (
  project_id BIGINT, project_number STRING, project_name STRING, developer_id BIGINT,
  master_developer_id BIGINT, area_id BIGINT, master_project_en STRING, project_status STRING,
  project_start_date STRING, project_end_date STRING, completion_date STRING,
  percent_completed STRING, source STRING
);
CREATE TABLE IF NOT EXISTS dld.core.dim_building (
  property_id BIGINT, building_number STRING, land_number STRING, area_id BIGINT, project_id BIGINT,
  master_project_en STRING, property_type_en STRING, property_sub_type_en STRING, floors STRING,
  flats STRING, is_free_hold STRING, creation_date STRING, source STRING
);