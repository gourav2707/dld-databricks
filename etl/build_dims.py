# Builds the 4 dimensions from raw, rebuilt whole on every run.
# Each dimension lists its sources in priority order: if the same id appears in
# several sources, the first source wins (newer extract-2 before extract-1).


def q(c):
    return "`" + c.replace("`", "``") + "`"


def col_expr(src_col, typ):
    if src_col is None:
        return f"CAST(NULL AS {typ})"
    v = f"nullif(trim({q(src_col)}), '')"                          # blank -> NULL
    if typ == "STRING":
        return v
    return f"try_cast(regexp_replace({v}, '[.]0+$', '') AS {typ})"  # '334.0' -> 334


AREA = {"area_id": "area_id", "area_name_en": "area_name_en", "area_name_ar": "area_name_ar"}
DEV_COLS = ["developer_id", "developer_number", "developer_name_en", "developer_name_ar",
            "license_number", "legal_status_en", "registration_date"]
PROJ_COLS = ["project_id", "project_number", "project_name", "developer_id", "master_developer_id",
             "area_id", "master_project_en", "project_status", "project_start_date",
             "project_end_date", "completion_date", "percent_completed"]
BLD_COLS = ["property_id", "building_number", "land_number", "area_id", "project_id",
            "master_project_en", "property_type_en", "property_sub_type_en", "floors",
            "flats", "is_free_hold", "creation_date"]
IDS = {"area_id", "developer_id", "master_developer_id", "project_id", "property_id"}


def typed(cols):
    return [(c, "BIGINT" if c in IDS else "STRING") for c in cols]


DIMS = {
    "dim_area": {
        "key": "area_id", "label": "area_name_en",
        "columns": typed(["area_id", "area_name_en", "area_name_ar", "municipality_number"]),
        "sources": [
            ("e2_lkp_areas", {"area_id": "area_id", "area_name_en": "name_en",
                              "area_name_ar": "name_ar", "municipality_number": "municipality_number"}),
            ("e2_projects", AREA), ("e1_projects", AREA),
            ("e2_buildings", AREA), ("e1_buildings", AREA),
            ("e2_transactions", AREA), ("e1_transactions", AREA),
        ],
    },
    "dim_developer": {
        "key": "developer_id", "label": "developer_name_en",
        "columns": typed(DEV_COLS),
        "sources": [
            ("e2_developers", {c: c for c in DEV_COLS}),
            ("e1_developers", {c: c for c in DEV_COLS}),
            ("e2_projects", {"developer_id": "developer_id", "developer_number": "developer_number",
                             "developer_name_en": "developer_name"}),
            ("e1_projects", {"developer_id": "developer_id", "developer_number": "developer_number",
                             "developer_name_en": "developer_name"}),
            ("e2_projects", {"developer_id": "master_developer_id", "developer_number": "master_developer_number",
                             "developer_name_en": "master_developer_name"}),
            ("e1_projects", {"developer_id": "master_developer_id", "developer_number": "master_developer_number",
                             "developer_name_en": "master_developer_name"}),
        ],
    },
    "dim_project": {
        "key": "project_id", "label": "project_name",
        "columns": typed(PROJ_COLS),
        "sources": [
            ("e2_projects", {c: c for c in PROJ_COLS}),
            ("e1_projects", {c: c for c in PROJ_COLS}),
            ("e2_buildings", {"project_id": "project_id", "project_name": "project_name_en",
                              "area_id": "area_id", "master_project_en": "master_project_en"}),
            ("e1_buildings", {"project_id": "project_id", "project_name": "project_name_en",
                              "area_id": "area_id", "master_project_en": "master_project_en"}),
        ],
    },
    "dim_building": {
        "key": "property_id", "label": "building_number",
        "columns": typed(BLD_COLS),
        "sources": [
            ("e2_buildings", {c: c for c in BLD_COLS}),
            ("e1_buildings", {c: c for c in BLD_COLS}),
        ],
    },
}


def special_row(dim, key_value, label):
    parts = []
    for col, typ in dim["columns"]:
        if col == dim["key"]:
            parts.append(f"CAST({key_value} AS {typ})")
        elif col == dim["label"]:
            parts.append(f"'{label}'")
        else:
            parts.append(f"CAST(NULL AS {typ})")
    return "SELECT " + ", ".join(parts) + ", 'special'"


def dim_sql(name):
    dim = DIMS[name]
    cols = [c for c, _ in dim["columns"]]
    key = q(dim["key"])
    selects = []
    for prio, (table, mapping) in enumerate(dim["sources"], start=1):
        exprs = ", ".join(f"{col_expr(mapping.get(c), t)} AS {q(c)}" for c, t in dim["columns"])
        selects.append(f"SELECT {exprs}, '{table}' AS source, {prio} AS _prio, _file_id, _row_num "
                       f"FROM dld.raw.{table}")
    union = "\nUNION ALL\n".join(selects)
    col_list = ", ".join(q(c) for c in cols + ["source"])
    return f"""
        INSERT OVERWRITE dld.core.{name} ({col_list})
        SELECT {col_list} FROM (
            SELECT *, row_number() OVER (PARTITION BY {key}
                                         ORDER BY _prio, _file_id DESC, _row_num DESC) AS _rn
            FROM ({union}) s
            WHERE {key} > 0
        ) WHERE _rn = 1
        UNION ALL {special_row(dim, -1, 'Unknown')}
        UNION ALL {special_row(dim, -2, 'Not matched')}
    """


def build_dims(spark):
    for name in DIMS:
        spark.sql(dim_sql(name))
        n = spark.table(f"dld.core.{name}").count()
        print(f"{name}: {n} rows")