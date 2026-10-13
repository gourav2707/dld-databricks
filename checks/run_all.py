import os, uuid
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.getOrCreate()
run_id = str(uuid.uuid4())
results = []

def check(name, passed, detail):
    results.append((run_id, name, bool(passed), str(detail)))

need = {"raw", "stg", "core", "mart", "meta"}
schemas = {r[0] for r in spark.sql("SHOW SCHEMAS IN dld").collect()}
check("schemas_exist", need <= schemas, sorted(need - schemas) or "all 5 present")

vols = {r.volume_name for r in spark.sql("SHOW VOLUMES IN dld.raw").collect()}
check("volumes_exist", {"landing", "checkpoints"} <= vols, sorted(vols))

n = spark.table("dld.meta.schema_migration").count()
check("migrations_applied", n >= 2, f"{n} rows in ledger")

files = sum(len(f) for _, _, f in os.walk("/Volumes/dld/raw/landing"))
check("landing_has_15_files", files == 15, f"{files} files")

(spark.createDataFrame(results, "run_id string, check_name string, passed boolean, detail string")
      .withColumn("checked_at", F.current_timestamp())
      .write.mode("append").saveAsTable("dld.meta.check_result"))

failed = [r[1] for r in results if not r[2]]
for r in results:
    print("PASS" if r[2] else "FAIL", r[1], "-", r[3])
if failed:
    raise Exception(f"Checks failed: {failed}")