import hashlib, os, re
from fnmatch import fnmatchcase

LANDING = "/Volumes/dld/raw/landing"
REGISTRY = "dld.meta.file_registry"

# raw table -> (folder under landing, file name pattern, format)
TABLES = {
    "e1_buildings":              ("extract-1", "Buildings.csv", "csv"),
    "e1_developers":             ("extract-1", "Developers.csv", "csv"),
    "e1_projects":               ("extract-1", "Projects.csv", "csv"),
    "e1_transactions":           ("extract-1", "dld_transactions-open.csv", "csv"),
    "e1_residential_sale_index": ("extract-1", "dld_residential_sale_index-open.xlsx", "xlsx"),
    "e2_buildings":              ("extract-2", "buildings_*.xlsx", "xlsx"),
    "e2_developers":             ("extract-2", "developers_*.xlsx", "xlsx"),
    "e2_lkp_areas":              ("extract-2", "lkp_areas_*.xlsx", "xlsx"),
    "e2_lkp_transaction_groups": ("extract-2", "lkp_transaction_groups_*.xlsx", "xlsx"),
    "e2_projects":               ("extract-2", "projects_*.xlsx", "xlsx"),
    "e2_real_estate_permits":    ("extract-2", "real_estate_permits_*.xlsx", "xlsx"),
    "e2_residential_sale_index": ("extract-2", "residential_sale_index_*.xlsx", "xlsx"),
    "e2_transactions":           ("extract-2", "transactions_*.csv", "csv"),
    "transactions_daily":        ("landing",   "transactions-*.csv", "csv"),
}

# tables that arrive split into parts: never load until every part is here
EXPECTED_PARTS = {"e2_transactions": 2}


def match_table(rel_path):
    folder, _, name = rel_path.rpartition("/")
    for table, (f, pattern, fmt) in TABLES.items():
        if folder == f and fnmatchcase(name, pattern):
            return table, fmt
    return None, None


def part_no(name):
    m = re.search(r"_(\d{4})(?: \(\d+\))?\.\w+$", name)
    return int(m.group(1)) if m else None


def missing_parts(table, parts):
    need = EXPECTED_PARTS.get(table)
    if not need:
        return []
    return sorted(set(range(1, need + 1)) - {p for p in parts if p})


def sha256_file(path, chunk=8 * 1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def register_files(spark):
    rows = spark.table(REGISTRY).select("file_path", "sha256", "size_bytes").collect()
    by_path = {r.file_path: r for r in rows}
    by_hash = {r.sha256: r.file_path for r in rows}
    new = []

    for root, _, names in os.walk(LANDING):
        for name in sorted(names):
            if not name.lower().endswith((".csv", ".xlsx")):
                continue
            path = f"{root}/{name}"
            size = os.path.getsize(path)
            if path in by_path:
                if by_path[path].size_bytes != size:
                    raise RuntimeError(f"{path} changed after it was registered")
                continue
            rel = path[len(LANDING) + 1:]
            table, fmt = match_table(rel)
            sha = sha256_file(path)
            if sha in by_hash:
                status, note = "duplicate", f"same content as {by_hash[sha]}"
            elif table is None:
                status, note = "unmatched", "no raw table rule for this file"
            else:
                status, note = "registered", None
            by_hash.setdefault(sha, path)
            new.append((path, table, fmt, part_no(name), size, sha, status, note))
            print(status.ljust(11), rel)

    if new:
        schema = ("file_path string, raw_table string, file_format string, part_no int, "
                  "size_bytes long, sha256 string, status string, note string")
        spark.createDataFrame(new, schema).createOrReplaceTempView("new_files")
        spark.sql(f"""
            INSERT INTO {REGISTRY}
              (file_path, raw_table, file_format, part_no, size_bytes, sha256, status, note, registered_at)
            SELECT *, current_timestamp() FROM new_files""")
    print(f"registered {len(new)} new file(s)")
    return len(new)