import os, shutil, zipfile
from etl.registry import REGISTRY
from etl.load_csv import LOAD_LOG, clean

CONVERTED = "/Volumes/dld/raw/converted"

# Strict OOXML uses different XML names for the same content; Databricks only reads the normal ones
STRICT_TO_TRANSITIONAL = [
    (b"http://purl.oclc.org/ooxml/spreadsheetml/main",
     b"http://schemas.openxmlformats.org/spreadsheetml/2006/main"),
    (b"http://purl.oclc.org/ooxml/officeDocument/relationships",
     b"http://schemas.openxmlformats.org/officeDocument/2006/relationships"),
    (b"http://purl.oclc.org/ooxml/drawingml/main",
     b"http://schemas.openxmlformats.org/drawingml/2006/main"),
    (b' conformance="strict"', b""),
]


def q(name):
    return "`" + name.replace("`", "``") + "`"


def strict_to_transitional_xml(data):
    for a, b in STRICT_TO_TRANSITIONAL:
        data = data.replace(a, b)
    return data


def is_strict(path):
    with zipfile.ZipFile(path) as z:
        try:
            return STRICT_TO_TRANSITIONAL[0][0] in z.read("xl/workbook.xml")
        except KeyError:
            return False


def to_transitional(path):
    name = os.path.basename(path)
    tmp = f"/tmp/{name}"   # a zip cannot be written straight into a volume
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.endswith((".xml", ".rels")):
                data = strict_to_transitional_xml(data)
            zout.writestr(item, data)
    dst = f"{CONVERTED}/{name}"
    shutil.copy(tmp, dst)
    return dst


def load_xlsx(spark, table, run_id):
    target = f"dld.raw.{table}"
    files = (spark.table(REGISTRY)
             .where(f"raw_table = '{table}' AND status = 'registered'")
             .select("file_id", "file_path").collect())
    if not files:
        print(f"{table}: 0 new file(s)")
        return 0

    for f in files:
        try:
            src, method, note = f.file_path, "copy_into", None
            if is_strict(f.file_path):
                src = to_transitional(f.file_path)
                method, note = "copy_into_converted", f"Strict OOXML converted to {src}"

            cols = spark.read.format("excel").option("headerRows", 1).load(src).columns
            names = [clean(c) for c in cols]
            if len(set(names)) != len(names):
                raise RuntimeError(f"{table}: duplicate column names after cleaning: {names}")

            ddl = ", ".join(f"{q(n)} STRING" for n in names)
            spark.sql(f"""CREATE TABLE IF NOT EXISTS {target} ({ddl},
                          _file_id BIGINT, _row_num BIGINT, _ingested_at TIMESTAMP, _seq BIGINT)""")

            # Excel guesses types and that cannot be turned off, so cast every column back to text
            select = ", ".join(f"CAST({q(c)} AS STRING) AS {q(n)}" for c, n in zip(cols, names))
            spark.sql(f"""
                COPY INTO {target}
                FROM (SELECT {select},
                             CAST({f.file_id} AS BIGINT)   AS _file_id,
                             CAST(NULL AS BIGINT)          AS _row_num,
                             current_timestamp()           AS _ingested_at,
                             monotonically_increasing_id() AS _seq
                      FROM '{src}')
                FILEFORMAT = EXCEL
                FORMAT_OPTIONS ('headerRows' = '1')
            """)

            # an .xlsx file is read in one piece, so _seq follows the row order of the sheet
            spark.sql(f"""
                MERGE INTO {target} t
                USING (SELECT _seq, row_number() OVER (ORDER BY _seq) AS rn
                       FROM {target} WHERE _file_id = {f.file_id}) s
                ON t._file_id = {f.file_id} AND t._seq = s._seq
                WHEN MATCHED AND t._row_num IS NULL THEN UPDATE SET _row_num = s.rn
            """)

            n = spark.sql(f"SELECT count(*) AS c FROM {target} WHERE _file_id = {f.file_id}").first().c
            spark.sql(f"""INSERT INTO {LOAD_LOG} VALUES
                          (:run_id, :fid, :path, :target, :method, :n, 'loaded', :note, current_timestamp())""",
                      args={"run_id": run_id, "fid": f.file_id, "path": f.file_path, "target": target,
                            "method": method, "n": n, "note": note})
            spark.sql(f"UPDATE {REGISTRY} SET status = 'loaded' WHERE file_id = {f.file_id}")
            print(f"{table}: {n} rows from {f.file_path.rsplit('/', 1)[-1]}" + (" (converted)" if note else ""))

        except Exception as e:
            spark.sql(f"""INSERT INTO {LOAD_LOG} VALUES
                          (:run_id, :fid, :path, :target, 'copy_into', 0, 'failed', :msg, current_timestamp())""",
                      args={"run_id": run_id, "fid": f.file_id, "path": f.file_path,
                            "target": target, "msg": str(e)[:500]})
            raise
    return len(files)