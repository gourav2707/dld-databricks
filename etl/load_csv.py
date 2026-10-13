import re
from pyspark.sql import functions as F, Window
from etl.registry import TABLES, LANDING, REGISTRY, missing_parts

CHECKPOINTS = "/Volumes/dld/raw/checkpoints"
LOAD_LOG = "dld.meta.load_log"
GOOD = "status IN ('registered', 'loaded')"


def clean(name):
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def load_csv(spark, table, run_id):
    folder, pattern, fmt = TABLES[table]
    target = f"dld.raw.{table}"

    reg = spark.table(REGISTRY).where(F.col("raw_table") == table).where(GOOD)
    files = reg.select("file_id", "file_path", "part_no").collect()
    if not files:
        print(f"{table}: no registered files, skipped")
        return 0
    gap = missing_parts(table, [r.part_no for r in files])
    if gap:
        raise RuntimeError(f"{table}: refusing to load, missing part(s) {gap}")

    # one input split per file, so the read order of rows inside a file is kept
    spark.conf.set("spark.sql.files.maxPartitionBytes", "1g")

    stream = (spark.readStream.format("cloudFiles")
              .option("cloudFiles.format", "csv")
              .option("cloudFiles.inferColumnTypes", "false")      # every column as string
              .option("cloudFiles.schemaLocation", f"{CHECKPOINTS}/{table}/schema")
              .option("header", "true")
              .option("pathGlobFilter", pattern)
              .load(f"{LANDING}/{folder}")
              .withColumn("_file_path",
                          F.expr("url_decode(regexp_replace(_metadata.file_path, '^dbfs:', ''))")))

    def write_batch(batch, batch_id):
        s = batch.sparkSession
        ids = (s.table(REGISTRY).where(F.col("raw_table") == table).where(GOOD)
                .select(F.col("file_id").alias("_file_id"), F.col("file_path").alias("_file_path")))
        known = {r._file_path for r in ids.collect()}
        seen = {r._file_path for r in batch.select("_file_path").distinct().collect()}
        if seen - known:
            raise RuntimeError(f"{table}: file(s) not in registry: {sorted(seen - known)}")

        batch = batch.toDF(*[c if c.startswith("_") else clean(c) for c in batch.columns])
        w = Window.partitionBy("_file_path").orderBy("_seq")
        out = (batch.withColumn("_seq", F.monotonically_increasing_id())
                    .withColumn("_row_num", F.row_number().over(w))
                    .join(F.broadcast(ids), "_file_path", "left")
                    .withColumn("_ingested_at", F.current_timestamp())
                    .drop("_seq"))
        (out.write.format("delta").mode("append")
            .option("txnAppId", f"raw_{table}").option("txnVersion", batch_id)  # safe re-try
            .saveAsTable(target))

    (stream.writeStream.foreachBatch(write_batch)
           .option("checkpointLocation", f"{CHECKPOINTS}/{table}/stream")
           .trigger(availableNow=True)
           .start().awaitTermination())

    if not spark.catalog.tableExists(target):
        return 0
    n = spark.sql(f"""
        INSERT INTO {LOAD_LOG}
        SELECT :run_id, r._file_id, g.file_path, :target, 'auto_loader', r.n, 'loaded', NULL, current_timestamp()
        FROM (SELECT _file_id, count(*) AS n FROM {target} GROUP BY _file_id) r
        JOIN {REGISTRY} g ON g.file_id = r._file_id
        WHERE r._file_id NOT IN (SELECT file_id FROM {LOAD_LOG}
                                 WHERE target_table = :target AND status = 'loaded')
    """, args={"run_id": run_id, "target": target}).first()["num_inserted_rows"]
    spark.sql(f"""UPDATE {REGISTRY} SET status = 'loaded'
                  WHERE file_id IN (SELECT file_id FROM {LOAD_LOG} WHERE target_table = :target)""",
              args={"target": target})
    print(f"{table}: {n} new file(s) logged")
    return n