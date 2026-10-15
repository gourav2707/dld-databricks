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