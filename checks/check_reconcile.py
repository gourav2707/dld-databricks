# D5: compare our median residential sale price with DLD's published price index,
# at monthly, quarterly and yearly grain.
import uuid
from pyspark.sql import functions as F

FACT = "dld.core.fact_transaction"
INDEX = "dld.raw.e2_residential_sale_index"
RESULT = "dld.meta.reconcile_result"
SALES = "trans_group = 'Sales' AND property_usage = 'Residential' AND amount > 0"
SEGMENTS = {"all": "TRUE",
            "flat": "property_sub_type = 'Flat'",
            "villa": "(property_sub_type = 'Villa' OR property_type = 'Villa')"}
GRAINS = {"monthly": "MM", "quarterly": "QUARTER", "yearly": "YEAR"}

# Set AFTER a measured run, e.g. {"quarterly": 0.8}. None = report only.
# Measured on 15 Oct 2026 (quarterly): level_corr 0.589-0.629, median_ratio 0.903-1.069.
# Lines set below the measurements with a margin. Correlation is moderate because DLD's
# index adjusts for property mix and a raw median does not.
THRESHOLDS = {"quarterly": {"level_corr_min": 0.5, "ratio_min": 0.8, "ratio_max": 1.25}}


def series_sql(grain="monthly"):
    unit = GRAINS[grain]
    # the median of a period is computed from that period's rows: medians cannot be averaged
    ours = " UNION ALL ".join(
        f"SELECT '{s}' AS segment, trunc(instance_date, '{unit}') AS period, "
        f"median(amount) AS our_median, count(*) AS n "
        f"FROM {FACT} WHERE {SALES} AND {cond} GROUP BY trunc(instance_date, '{unit}')"
        for s, cond in SEGMENTS.items())
    dld = " UNION ALL ".join(
        f"SELECT '{s}' AS segment, trunc(to_date(substr(first_date_of_month, 1, 10)), '{unit}') AS period, "
        f"try_cast({s}_{grain}_price_index AS DOUBLE) AS dld_price FROM {INDEX} "
        f"WHERE try_cast({s}_{grain}_price_index AS DOUBLE) IS NOT NULL"
        for s in SEGMENTS)
    return f"""
        SELECT o.segment, o.period, o.our_median, o.n, d.dld_price,
               CAST(o.our_median AS DOUBLE) / d.dld_price AS ratio
        FROM ({ours}) o JOIN ({dld}) d ON o.segment = d.segment AND o.period = d.period"""


def metrics_sql(grain):
    return f"""
        WITH s AS ({series_sql(grain)}),
        c AS (SELECT *,
                CAST(our_median AS DOUBLE) / lag(CAST(our_median AS DOUBLE)) OVER (PARTITION BY segment ORDER BY period) - 1 AS our_chg,
                dld_price / lag(dld_price) OVER (PARTITION BY segment ORDER BY period) - 1 AS dld_chg
              FROM s)
        SELECT segment, count(*) AS periods, min(period) AS first_period, max(period) AS last_period,
               round(corr(CAST(our_median AS DOUBLE), dld_price), 3) AS level_corr,
               round(corr(our_chg, dld_chg), 3) AS change_corr,
               round(median(ratio), 3) AS median_ratio
        FROM c GROUP BY segment ORDER BY segment"""


def run(spark):
    run_id = str(uuid.uuid4())
    out = []
    for grain in GRAINS:
        for r in spark.sql(metrics_sql(grain)).collect():
            passed = None   
            t = (THRESHOLDS or {}).get(grain)
            if t:
                passed = (r.level_corr is not None and r.level_corr >= t["level_corr_min"]
                          and t["ratio_min"] <= r.median_ratio <= t["ratio_max"])
            out.append((run_id, r.segment, r.periods, r.first_period, r.last_period,
                        r.level_corr, r.change_corr, r.median_ratio, passed, grain))
            print(f"{grain:9} {r.segment:6} periods={r.periods:<4} level_corr={r.level_corr}  "
                  f"change_corr={r.change_corr}  median_ratio={r.median_ratio}  passed={passed}")
    schema = ("run_id string, segment string, months long, first_month date, last_month date, "
              "level_corr double, change_corr double, median_ratio double, passed boolean, grain string")
    df = spark.createDataFrame(out, schema).withColumn("checked_at", F.current_timestamp())
    df.select("run_id", "segment", "months", "first_month", "last_month", "level_corr", "change_corr",
              "median_ratio", "passed", "checked_at", "grain").write.mode("append").saveAsTable(RESULT)
    failed = [f"{o[9]}/{o[1]}" for o in out if o[8] is False]
    if failed:
        raise Exception(f"Reconciliation failed for: {failed}")