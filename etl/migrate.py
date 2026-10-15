import hashlib
from pathlib import Path

LEDGER = "dld.meta.schema_migration"


def file_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def split_sql(text):
    lines = [l for l in text.splitlines() if not l.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def selected(names, upto=None):
    # upto="004" applies 001..004 only, so each milestone applies just its own migrations
    return [n for n in sorted(names) if upto is None or n[:3] <= upto]


def run_migrations(spark, ddl_dir, upto=None):
    spark.sql("CREATE CATALOG IF NOT EXISTS dld")
    spark.sql("CREATE SCHEMA IF NOT EXISTS dld.meta")
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {LEDGER} (
        file_name STRING, sha256 STRING, statements INT, applied_at TIMESTAMP)""")

    applied = {r.file_name: r.sha256 for r in spark.table(LEDGER).collect()}

    for name in selected([p.name for p in Path(ddl_dir).glob("*.sql")], upto):
        text = (Path(ddl_dir) / name).read_text()
        h = file_hash(text)
        if name in applied:
            if applied[name] != h:
                raise RuntimeError(f"{name} was edited after it ran. Add a new migration file instead.")
            print("skip   ", name)
            continue
        stmts = split_sql(text)
        for s in stmts:
            spark.sql(s)
        spark.sql(f"INSERT INTO {LEDGER} VALUES (:f, :h, :n, current_timestamp())",
                  args={"f": name, "h": h, "n": len(stmts)})
        print("applied", name, f"({len(stmts)} statements)")