# D4: conform the two source shapes (bulk = e1 + e2, daily) into dld.stg.transaction.
# Rows that cannot be used go to dld.stg.transaction_quarantine with reason codes.
from etl.resolve_area import clean_id

BULK_TABLES = ["e2_transactions", "e1_transactions"]
DAILY_TABLE = "transactions_daily"
NULL_TOKENS = ("", "NONE", "NULL", "N/A", "NA", "-")


def q(c):
    return "`" + c.replace("`", "``") + "`"


def clean(col):
    # trim, single spaces, and every "means nothing" word becomes NULL
    tokens = ", ".join(f"'{t}'" for t in NULL_TOKENS)
    return (f"CASE WHEN upper(trim({col})) IN ({tokens}) THEN NULL "
            f"ELSE regexp_replace(trim({col}), ' +', ' ') END")


def to_int(col):
    return f"try_cast(regexp_replace({col}, '[.]0+$', '') AS INT)"


DMY = "'^([0-9]{2})-([0-9]{2})-([0-9]{4})'"


def to_date(col):
    # e1 writes dd-MM-yyyy, e2 and daily write yyyy-MM-dd: turn dd-MM-yyyy into yyyy-MM-dd first
    return "try_cast(regexp_replace(" + col + ", " + DMY + ", '$3-$2-$1') AS DATE)"


RAW_COLS = ["transaction_key", "date_raw", "trans_group", "procedure_name", "reg_type", "is_free_hold",
            "property_usage", "property_type", "property_sub_type", "rooms", "area_id_raw", "area_en",
            "project_number", "project_name", "master_project", "building_name",
            "amount_raw", "procedure_area_raw", "actual_area_raw", "meter_sale_price_raw",
            "rent_value_raw", "meter_rent_price_raw", "parking_raw", "has_parking_raw",
            "parties1_raw", "parties2_raw", "parties3_raw", "buyers_raw", "sellers_raw",
            "nearest_metro", "nearest_mall", "nearest_landmark"]

BULK_MAP = {
    "transaction_key": "transaction_id", "date_raw": "instance_date", "trans_group": "trans_group_en",
    "procedure_name": "procedure_name_en", "reg_type": "reg_type_en", "property_usage": "property_usage_en",
    "property_type": "property_type_en", "property_sub_type": "property_sub_type_en", "rooms": "rooms_en",
    "area_id_raw": "area_id", "area_en": "area_name_en", "project_number": "project_number",
    "project_name": "project_name_en", "master_project": "master_project_en", "building_name": "building_name_en",
    "amount_raw": "actual_worth", "procedure_area_raw": "procedure_area", "meter_sale_price_raw": "meter_sale_price",
    "rent_value_raw": "rent_value", "meter_rent_price_raw": "meter_rent_price", "has_parking_raw": "has_parking",
    "parties1_raw": "no_of_parties_role_1", "parties2_raw": "no_of_parties_role_2",
    "parties3_raw": "no_of_parties_role_3", "nearest_metro": "nearest_metro_en",
    "nearest_mall": "nearest_mall_en", "nearest_landmark": "nearest_landmark_en",
}
DAILY_MAP = {
    "transaction_key": "transaction_number", "date_raw": "instance_date", "trans_group": "group_en",
    "procedure_name": "procedure_en", "reg_type": "is_offplan_en", "is_free_hold": "is_free_hold_en",
    "property_usage": "usage_en", "property_type": "prop_type_en", "property_sub_type": "prop_sb_type_en",
    "rooms": "rooms_en", "area_en": "area_en", "project_name": "project_en", "master_project": "master_project_en",
    "amount_raw": "trans_value", "procedure_area_raw": "procedure_area", "actual_area_raw": "actual_area",
    "parking_raw": "parking", "buyers_raw": "total_buyer", "sellers_raw": "total_seller",
    "nearest_metro": "nearest_metro_en", "nearest_mall": "nearest_mall_en", "nearest_landmark": "nearest_landmark_en",
}

# columns whose words are translated to the bulk vocabulary: unified name -> (bulk column, daily column)
TERMS = {"trans_group": ("trans_group_en", "group_en"), "procedure_name": ("procedure_name_en", "procedure_en"),
         "reg_type": ("reg_type_en", "is_offplan_en"), "property_usage": ("property_usage_en", "usage_en"),
         "property_type": ("property_type_en", "prop_type_en"),
         "property_sub_type": ("property_sub_type_en", "prop_sb_type_en"), "rooms": ("rooms_en", "rooms_en")}

# daily words that differ from bulk words; None = no bulk equivalent (kept as NULL and flagged)
OVERRIDES = {
    ("reg_type", "Off-Plan"): ("Off-Plan Properties", "daily says Off-Plan"),
    ("reg_type", "Ready"): ("Existing Properties", "daily says Ready"),
    ("trans_group", "Mortgage"): ("Mortgages", "daily singular, bulk plural"),
    ("procedure_name", "Sale"): ("Sell", "daily says Sale, bulk says Sell"),
    ("property_sub_type", "Commercial"): (None, "usage word found in daily sub-type column"),
    ("property_sub_type", "Residential"): (None, "usage word found in daily sub-type column"),
}

# bulk is the standard vocabulary, except where the bulk itself is wrong
BULK_OVERRIDES = {
    ("property_usage", "أخرى"): ("Other", "Arabic word for Other found in the English column (e2)"),
}

NUMS = {"amount": ("amount_raw", "DECIMAL(18,2)"), "procedure_area": ("procedure_area_raw", "DECIMAL(14,2)"),
        "actual_area": ("actual_area_raw", "DECIMAL(14,2)"),
        "meter_sale_price": ("meter_sale_price_raw", "DECIMAL(18,2)"),
        "rent_value": ("rent_value_raw", "DECIMAL(18,2)"),
        "meter_rent_price": ("meter_rent_price_raw", "DECIMAL(18,2)")}
INTS = {"n_parties_role_1": "parties1_raw", "n_parties_role_2": "parties2_raw",
        "n_parties_role_3": "parties3_raw", "n_buyers": "buyers_raw", "n_sellers": "sellers_raw",
        "has_parking": "has_parking_raw"}


def shape_select(shape, table, mapping):
    cols = [f"{clean(q(mapping[c])) if c in mapping else 'CAST(NULL AS STRING)'} AS {c}" for c in RAW_COLS]
    if shape == "daily":   # raw values exactly as stored, to join the area crosswalk
        xw = "area_en AS _xw_area, project_en AS _xw_project, master_project_en AS _xw_master"
    else:
        xw = "CAST(NULL AS STRING) AS _xw_area, CAST(NULL AS STRING) AS _xw_project, CAST(NULL AS STRING) AS _xw_master"
    return (f"SELECT '{shape}' AS source_shape, '{table}' AS source_table, _file_id, _row_num, "
            f"{', '.join(cols)}, {xw} FROM dld.raw.{table}")


def reason_exprs():
    r = ["CASE WHEN s.transaction_key IS NULL THEN 'MISSING_ID' END",
         "CASE WHEN s.date_raw IS NULL THEN 'MISSING_DATE' END",
         f"CASE WHEN s.date_raw IS NOT NULL AND {to_date('s.date_raw')} IS NULL THEN 'BAD_DATE' END"]
    for name, (raw, typ) in NUMS.items():
        r.append(f"CASE WHEN s.{raw} IS NOT NULL AND try_cast(s.{raw} AS {typ}) IS NULL THEN 'BAD_NUMBER:{name}' END")
    for name, raw in INTS.items():
        r.append(f"CASE WHEN s.{raw} IS NOT NULL AND {to_int('s.' + raw)} IS NULL THEN 'BAD_NUMBER:{name}' END")
    return r


def build_term_map(spark):
    rows = []
    for term, (bcol, dcol) in TERMS.items():
        bulk_sql = " UNION ".join(f"SELECT DISTINCT {clean(bcol)} AS v FROM dld.raw.{t}" for t in BULK_TABLES)
        bulk = {r.v for r in spark.sql(bulk_sql).collect() if r.v is not None}
        daily = {r.v for r in spark.sql(f"SELECT DISTINCT {clean(dcol)} AS v FROM dld.raw.{DAILY_TABLE}").collect()
                 if r.v is not None}
        for t in sorted(bulk):
            std, note = BULK_OVERRIDES.get((term, t), (t, "standard term"))
            rows.append((term, "bulk", t, std, note))
        bulk = {BULK_OVERRIDES.get((term, t), (t,))[0] for t in bulk}   # vocabulary after fixes
        by_upper = {t.upper(): t for t in bulk}
        for t in sorted(daily):
            if (term, t) in OVERRIDES:
                std, note = OVERRIDES[(term, t)]
                if std is not None and std not in bulk:
                    std, note = None, f"UNMAPPED: override target '{OVERRIDES[(term, t)][0]}' is not a bulk term"
            elif t.upper() in by_upper:
                std, note = by_upper[t.upper()], "same word as bulk"
            else:
                std, note = None, "UNMAPPED: no bulk term"
            rows.append((term, "daily", t, std, note))
    spark.createDataFrame(rows, "term string, source_shape string, source_term string, std_term string, note string") \
         .createOrReplaceTempView("new_term_map")
    spark.sql("INSERT OVERWRITE dld.stg.term_map SELECT * FROM new_term_map")
    print(f"term_map: {len(rows)} rows")


def conformed_view_sql():
    shapes = [shape_select("bulk", t, BULK_MAP) for t in BULK_TABLES] + [shape_select("daily", DAILY_TABLE, DAILY_MAP)]
    joins, std, unmapped = [], [], []
    for t in TERMS:
        joins.append(f"LEFT JOIN dld.stg.term_map tm_{t} ON tm_{t}.term = '{t}' "
                     f"AND tm_{t}.source_shape = s.source_shape AND tm_{t}.source_term = s.{t}")
        std.append(f"tm_{t}.std_term AS {t}_std")
        unmapped.append(f"CASE WHEN s.{t} IS NOT NULL AND tm_{t}.std_term IS NULL THEN '{t}' END")
    return f"""
        CREATE OR REPLACE TEMP VIEW stg_conformed AS
        WITH s AS ({' UNION ALL '.join(shapes)})
        SELECT s.*, {', '.join(std)},
               filter(array({', '.join(unmapped)}), v -> v IS NOT NULL) AS unmapped_terms,
               CASE WHEN s.source_shape = 'daily' THEN coalesce(xw.area_id, -2)
                    WHEN s.area_id_raw IS NULL THEN -1
                    WHEN da.area_id IS NULL THEN -2
                    ELSE da.area_id END AS area_id,
               CASE WHEN s.source_shape = 'daily' THEN coalesce(xw.rung_name, 'not_in_crosswalk')
                    WHEN s.area_id_raw IS NULL THEN 'missing'
                    WHEN da.area_id IS NULL THEN 'unknown_id'
                    ELSE 'source_id' END AS area_source,
               filter(array({', '.join(reason_exprs())}), r -> r IS NOT NULL) AS reasons
        FROM s
        {' '.join(joins)}
        LEFT JOIN dld.core.dim_area da ON da.area_id = {clean_id('s.area_id_raw')} AND da.area_id > 0
        LEFT JOIN dld.core.area_crosswalk xw ON s.source_shape = 'daily'
             AND xw.area_en <=> s._xw_area AND xw.project_en <=> s._xw_project
             AND xw.master_project_en <=> s._xw_master"""


def stg_columns():
    cols = [("source_shape", "source_shape"), ("source_table", "source_table"), ("_file_id", "_file_id"),
            ("_row_num", "_row_num"), ("transaction_key", "transaction_key"),
            ("instance_date", to_date("date_raw")),
            ("instance_ts", "CASE WHEN source_shape = 'daily' THEN try_cast(date_raw AS TIMESTAMP_NTZ) END")]
    cols += [(t, f"{t}_std") for t in ["trans_group", "procedure_name", "reg_type"]]
    cols += [("is_free_hold", "is_free_hold")]
    cols += [(t, f"{t}_std") for t in ["property_usage", "property_type", "property_sub_type", "rooms"]]
    cols += [(c, c) for c in ["area_id", "area_source", "area_en", "project_number", "project_name",
                              "master_project", "building_name"]]
    cols += [(name, f"try_cast({raw} AS {typ})") for name, (raw, typ) in NUMS.items()]
    cols += [("has_parking", "CASE WHEN source_shape = 'daily' THEN CASE WHEN parking_raw IS NULL THEN NULL ELSE 1 END "
                             f"ELSE {to_int('has_parking_raw')} END"),
             ("parking_raw", "parking_raw")]
    cols += [(name, to_int(raw)) for name, raw in INTS.items() if name != "has_parking"]
    cols += [(c, c) for c in ["nearest_metro", "nearest_mall", "nearest_landmark", "unmapped_terms"]]
    cols += [("staged_at", "current_timestamp()")]
    return cols


def conform_all(spark):
    build_term_map(spark)
    spark.sql(conformed_view_sql())

    cols = stg_columns()
    spark.sql(f"""INSERT OVERWRITE dld.stg.transaction ({', '.join(c for c, _ in cols)})
                  SELECT {', '.join(e for _, e in cols)} FROM stg_conformed WHERE size(reasons) = 0""")
    raw_struct = ", ".join(RAW_COLS)
    spark.sql(f"""INSERT OVERWRITE dld.stg.transaction_quarantine
                  SELECT source_shape, source_table, _file_id, _row_num, transaction_key, reasons,
                         to_json(struct({raw_struct})), current_timestamp()
                  FROM stg_conformed WHERE size(reasons) > 0""")

    raw = sum(spark.table(f"dld.raw.{t}").count() for t in BULK_TABLES + [DAILY_TABLE])
    stg = spark.table("dld.stg.transaction").count()
    qua = spark.table("dld.stg.transaction_quarantine").count()
    print(f"raw {raw:,} = staged {stg:,} + quarantined {qua:,}  ->  {'OK' if raw == stg + qua else 'MISMATCH'}")
    if raw != stg + qua:
        raise RuntimeError("Rows were lost or duplicated between raw and staging")