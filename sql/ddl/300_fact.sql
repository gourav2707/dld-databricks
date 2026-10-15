-- D5: fact = current state (SCD1), history = every version (SCD2). Liquid clustering instead of partitions.
CREATE TABLE IF NOT EXISTS dld.core.fact_transaction (
  transaction_key STRING, source_shape STRING, date_key INT, instance_date DATE, instance_ts TIMESTAMP_NTZ,
  area_id BIGINT, project_id BIGINT,
  trans_group STRING, procedure_name STRING, reg_type STRING, property_usage STRING,
  property_type STRING, property_sub_type STRING, rooms STRING,
  amount DECIMAL(18,2), procedure_area DECIMAL(14,2), actual_area DECIMAL(14,2),
  meter_sale_price DECIMAL(18,2), rent_value DECIMAL(18,2), has_parking INT,
  record_hash STRING, loaded_from STRING, _file_id BIGINT, _row_num BIGINT, updated_at TIMESTAMP
) CLUSTER BY (instance_date, area_id)
  TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported');
CREATE TABLE IF NOT EXISTS dld.core.fact_transaction_history (
  transaction_key STRING, source_shape STRING, date_key INT, instance_date DATE, instance_ts TIMESTAMP_NTZ,
  area_id BIGINT, project_id BIGINT,
  trans_group STRING, procedure_name STRING, reg_type STRING, property_usage STRING,
  property_type STRING, property_sub_type STRING, rooms STRING,
  amount DECIMAL(18,2), procedure_area DECIMAL(14,2), actual_area DECIMAL(14,2),
  meter_sale_price DECIMAL(18,2), rent_value DECIMAL(18,2), has_parking INT,
  record_hash STRING, loaded_from STRING, _file_id BIGINT, _row_num BIGINT,
  valid_from TIMESTAMP, valid_to TIMESTAMP, is_current BOOLEAN
) CLUSTER BY (transaction_key, instance_date)
  TBLPROPERTIES ('delta.feature.timestampNtz' = 'supported');