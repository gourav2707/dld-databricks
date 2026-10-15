-- D4: staging. Two source shapes (bulk, daily) conformed into one typed table, plus quarantine and term map
CREATE TABLE IF NOT EXISTS dld.stg.term_map (
  term STRING, source_shape STRING, source_term STRING, std_term STRING, note STRING
);
CREATE TABLE IF NOT EXISTS dld.stg.transaction (
  source_shape STRING, source_table STRING, _file_id BIGINT, _row_num BIGINT,
  transaction_key STRING, instance_date DATE, instance_ts TIMESTAMP_NTZ,
  trans_group STRING, procedure_name STRING, reg_type STRING, is_free_hold STRING,
  property_usage STRING, property_type STRING, property_sub_type STRING, rooms STRING,
  area_id BIGINT, area_source STRING, area_en STRING,
  project_number STRING, project_name STRING, master_project STRING, building_name STRING,
  amount DECIMAL(18,2), procedure_area DECIMAL(14,2), actual_area DECIMAL(14,2),
  meter_sale_price DECIMAL(18,2), rent_value DECIMAL(18,2), meter_rent_price DECIMAL(18,2),
  has_parking INT, parking_raw STRING,
  n_parties_role_1 INT, n_parties_role_2 INT, n_parties_role_3 INT, n_buyers INT, n_sellers INT,
  nearest_metro STRING, nearest_mall STRING, nearest_landmark STRING,
  unmapped_terms ARRAY<STRING>, staged_at TIMESTAMP
) TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported');
CREATE TABLE IF NOT EXISTS dld.stg.transaction_quarantine (
  source_shape STRING, source_table STRING, _file_id BIGINT, _row_num BIGINT,
  transaction_key STRING, reasons ARRAY<STRING>, raw_row STRING, quarantined_at TIMESTAMP
);