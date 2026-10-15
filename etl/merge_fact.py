# D5: merge staging into the fact (SCD1, current state) and its history (SCD2, every version).
# Batches are merged oldest first, so later extracts become newer versions.
from etl.resolve_area import norm

FACT = "dld.core.fact_transaction"
HIST = "dld.core.fact_transaction_history"
BATCHES = ["e1_transactions", "e2_transactions", "transactions_daily"]

# What counts as a real change. Place NAMES are left out on purpose: the same place is spelled
# differently between extracts (Marsa Dubai vs DUBAI MARINA) and would create fake versions.
# The place IDS (area_id, project_id) are in.
HASH_COLS = ["instance_date", "area_id", "project_id", "trans_group", "procedure_name", "reg_type",
             "property_usage", "property_type", "property_sub_type", "rooms", "amount",
             "procedure_area", "actual_area", "meter_sale_price", "rent_value", "has_parking"]

COLS = ["transaction_key", "source_shape", "date_key", "instance_date", "instance_ts", "area_id", "project_id",
        "trans_group", "procedure_name", "reg_type", "property_usage", "property_type", "property_sub_type",
        "rooms", "amount", "procedure_area", "actual_area", "meter_sale_price", "rent_value", "has_parking",
        "record_hash", "loaded_from", "_file_id", "_row_num"]


def hash_expr(cols=HASH_COLS):
    parts = ", ".join(f"coalesce(CAST({c} AS STRING), '<null>')" for c in cols)
    return f"sha2(concat_ws('|', {parts}), 256)"


def source_sql(batch):
    return f"""
        SELECT t.transaction_key, t.source_shape,
               CAST(date_format(t.instance_date, 'yyyyMMdd') AS INT) AS date_key,
               t.instance_date, t.instance_ts, t.area_id,
               CASE WHEN t.project_number IS NULL AND t.project_name IS NULL THEN -1
                    ELSE coalesce(p.project_id, b.project_id, -2) END AS project_id,
               t.trans_group, t.procedure_name, t.reg_type, t.property_usage, t.property_type,
               t.property_sub_type, t.rooms, t.amount, t.procedure_area, t.actual_area,
               t.meter_sale_price, t.rent_value, t.has_parking,
               '{batch}' AS loaded_from, t._file_id, t._row_num
        FROM dld.stg.transaction t
        LEFT JOIN (SELECT regexp_replace(project_number, '[.]0+$', '') AS pn, min(project_id) AS project_id
                   FROM dld.core.dim_project WHERE project_id > 0
                   GROUP BY 1 HAVING count(DISTINCT project_id) = 1) p
               ON t.source_shape = 'bulk' AND p.pn = regexp_replace(t.project_number, '[.]0+$', '')
        LEFT JOIN (SELECT name, project_id FROM dld.core.name_project_bridge WHERE n_project_ids = 1) b
               ON t.source_shape = 'daily' AND b.name = {norm('t.project_name')}
        WHERE t.source_table = '{batch}'"""


def scd1_sql():
    sets = ", ".join(f"{c} = s.{c}" for c in COLS if c != "transaction_key")
    cols = ", ".join(COLS)
    vals = ", ".join(f"s.{c}" for c in COLS)
    return f"""
        MERGE INTO {FACT} f
        USING fact_src s ON f.transaction_key = s.transaction_key
        WHEN MATCHED AND f.record_hash <> s.record_hash
                     AND {seq('s.loaded_from')} >= {seq('f.loaded_from')} THEN
          UPDATE SET {sets}, updated_at = current_timestamp()
        WHEN NOT MATCHED THEN
          INSERT ({cols}, updated_at) VALUES ({vals}, current_timestamp())"""


def scd2_sql():
    # one atomic MERGE: changed keys appear twice in the source, once with their key (to close
    # the old version) and once with a NULL key (never matches, so the new version is inserted)
    cols = ", ".join(COLS)
    vals = ", ".join(f"u.{c}" for c in COLS)
    return f"""
        MERGE INTO {HIST} h
        USING (
          SELECT s.transaction_key AS merge_key, s.* FROM fact_src s
          UNION ALL
          SELECT CAST(NULL AS STRING) AS merge_key, s.* FROM fact_src s
          JOIN {HIST} c ON c.transaction_key = s.transaction_key AND c.is_current
                       AND c.record_hash <> s.record_hash
                       AND {seq('s.loaded_from')} >= {seq('c.loaded_from')}
        ) u
        ON h.transaction_key = u.merge_key AND h.is_current
        WHEN MATCHED AND h.record_hash <> u.record_hash
                     AND {seq('u.loaded_from')} >= {seq('h.loaded_from')} THEN
          UPDATE SET is_current = false, valid_to = u.valid_from
        WHEN NOT MATCHED THEN
          INSERT ({cols}, valid_from, valid_to, is_current)
          VALUES ({vals}, u.valid_from, NULL, true)"""


def merge_batch(spark, batch):
    spark.sql(f"""CREATE OR REPLACE TEMP VIEW fact_src AS
                  SELECT *, {hash_expr()} AS record_hash, current_timestamp() AS valid_from
                  FROM ({source_sql(batch)}) x""")
    dups = spark.sql("SELECT transaction_key FROM fact_src GROUP BY 1 HAVING count(*) > 1 LIMIT 5").collect()
    if dups:
        raise RuntimeError(f"{batch}: same transaction twice in one batch: {[r[0] for r in dups]}")
    r1 = spark.sql(scd1_sql()).first().asDict()
    r2 = spark.sql(scd2_sql()).first().asDict()
    print(f"{batch:20} fact: +{r1['num_inserted_rows']:,} new, {r1['num_updated_rows']:,} changed | "
          f"history: +{r2['num_inserted_rows']:,} versions, {r2['num_updated_rows']:,} closed")


def merge_all(spark, batches=BATCHES):
    for b in batches:
        merge_batch(spark, b)


def seq(col):
    # batch order: an older batch may never overwrite a newer one
    whens = " ".join(f"WHEN '{b}' THEN {i}" for i, b in enumerate(BATCHES, start=1))
    return f"(CASE {col} {whens} END)"