# Bridges, area crosswalk and fuzzy review queue. Everything is rebuilt whole from data.

RUNGS = {
    1: "official_area_name",      # area_en = official name in dim_area
    2: "area_name_in_bulk",       # area_en = an area name used in bulk data
    3: "area_as_master_project",  # area_en = a master project name in bulk data
    4: "project_name",            # project_en -> project -> its area
    5: "master_project_column",   # master_project_en -> area
}
AREA_SOURCES = ["e2_transactions", "e1_transactions", "e2_projects", "e1_projects",
                "e2_buildings", "e1_buildings"]
TX = ["e2_transactions", "e1_transactions"]


def norm(col):
    # one normalisation used everywhere: trim, single spaces, upper case, blank -> NULL
    return f"nullif(upper(regexp_replace(trim({col}), ' +', ' ')), '')"


def clean_id(col):
    return f"try_cast(regexp_replace(nullif(trim({col}), ''), '[.]0+$', '') AS BIGINT)"


def area_bridge_sql():
    t = "\nUNION ALL\n".join(
        f"SELECT {clean_id('area_id')} AS area_id, {norm('area_name_en')} AS an, "
        f"{norm('master_project_en')} AS mp FROM dld.raw.{s}" for s in AREA_SOURCES)
    return f"""
        INSERT OVERWRITE dld.core.name_area_bridge
        WITH t AS ({t}),
        names AS (SELECT an AS name, 'area_name' AS via, area_id FROM t
                  UNION ALL SELECT mp, 'master_project', area_id FROM t)
        SELECT name, via, min(area_id), count(DISTINCT area_id),
               array_sort(collect_set(area_id)), count(*)
        FROM names WHERE name IS NOT NULL AND area_id > 0
        GROUP BY name, via"""


def project_bridge_sql():
    tx = "\nUNION ALL\n".join(
        f"SELECT DISTINCT regexp_replace(trim(project_number), '[.]0+$', '') AS pn, "
        f"{norm('project_name_en')} AS name FROM dld.raw.{s}" for s in TX)
    return f"""
        INSERT OVERWRITE dld.core.name_project_bridge
        WITH tx AS ({tx}),
        p AS (
          SELECT project_id, {norm('project_name')} AS name FROM dld.core.dim_project WHERE project_id > 0
          UNION ALL
          SELECT dp.project_id, tx.name FROM tx
          JOIN dld.core.dim_project dp ON regexp_replace(dp.project_number, '[.]0+$', '') = tx.pn
          WHERE dp.project_id > 0
        )
        SELECT name, min(project_id), count(DISTINCT project_id), array_sort(collect_set(project_id))
        FROM p WHERE name IS NOT NULL GROUP BY name"""


def developer_bridge_sql():
    parts = [f"SELECT developer_id, {norm('developer_name_en')} AS name FROM dld.core.dim_developer"]
    for s in ["e2_projects", "e1_projects"]:
        parts.append(f"SELECT {clean_id('developer_id')}, {norm('developer_name')} FROM dld.raw.{s}")
        parts.append(f"SELECT {clean_id('master_developer_id')}, {norm('master_developer_name')} FROM dld.raw.{s}")
    d = "\nUNION ALL\n".join(parts)
    return f"""
        INSERT OVERWRITE dld.core.developer_name_bridge
        WITH d AS ({d})
        SELECT name, min(developer_id), count(DISTINCT developer_id), array_sort(collect_set(developer_id))
        FROM d WHERE name IS NOT NULL AND developer_id > 0 GROUP BY name"""


def crosswalk_sql():
    rung_case = " ".join(f"WHEN r{i}.area_id IS NOT NULL THEN {i}" for i in RUNGS)
    name_case = " ".join(f"WHEN r{i}.area_id IS NOT NULL THEN '{n}'" for i, n in RUNGS.items())
    return f"""
        INSERT OVERWRITE dld.core.area_crosswalk
        WITH k AS (
          SELECT area_en, project_en, master_project_en, count(*) AS n_rows,
                 {norm('area_en')} AS a, {norm('project_en')} AS p, {norm('master_project_en')} AS m
          FROM dld.raw.transactions_daily GROUP BY area_en, project_en, master_project_en
        ),
        off AS (SELECT {norm('area_name_en')} AS name, min(area_id) AS area_id
                FROM dld.core.dim_area WHERE area_id > 0 GROUP BY 1 HAVING count(DISTINCT area_id) = 1),
        ba AS (SELECT name, area_id FROM dld.core.name_area_bridge WHERE via = 'area_name' AND n_area_ids = 1),
        bm AS (SELECT name, area_id FROM dld.core.name_area_bridge WHERE via = 'master_project' AND n_area_ids = 1),
        bp AS (SELECT b.name, dp.area_id FROM dld.core.name_project_bridge b
               JOIN dld.core.dim_project dp ON dp.project_id = b.project_id
               WHERE b.n_project_ids = 1 AND dp.area_id > 0)
        SELECT k.area_en, k.project_en, k.master_project_en, k.n_rows,
               coalesce(r1.area_id, r2.area_id, r3.area_id, r4.area_id, r5.area_id,
                        CASE WHEN k.a IS NULL THEN -1 ELSE -2 END),
               CASE {rung_case} ELSE 0 END,
               CASE {name_case} ELSE 'unresolved' END
        FROM k
        LEFT JOIN off r1 ON r1.name = k.a
        LEFT JOIN ba  r2 ON r2.name = k.a
        LEFT JOIN bm  r3 ON r3.name = k.a
        LEFT JOIN bp  r4 ON r4.name = k.p
        LEFT JOIN bm  r5 ON r5.name = k.m"""


def review_sql():
    # fuzzy matching may only SUGGEST: nothing here is ever applied automatically
    return f"""
        INSERT OVERWRITE dld.meta.crosswalk_review
        WITH u AS (SELECT DISTINCT {norm('area_en')} AS name FROM dld.core.area_crosswalk
                   WHERE rung = 0 AND area_id = -2),
        c AS (SELECT {norm('area_name_en')} AS candidate, area_id, 'official_area_name' AS via
              FROM dld.core.dim_area WHERE area_id > 0
              UNION ALL
              SELECT name, area_id, 'master_project' FROM dld.core.name_area_bridge
              WHERE via = 'master_project' AND n_area_ids = 1),
        s AS (SELECT u.name, c.candidate, c.area_id, c.via,
                     1 - levenshtein(u.name, c.candidate) / greatest(length(u.name), length(c.candidate)) AS score
              FROM u CROSS JOIN c),
        best AS (SELECT *, row_number() OVER (PARTITION BY name ORDER BY score DESC, candidate) AS rn FROM s)
        SELECT name, candidate, area_id, via, round(score, 3), 'pending', current_timestamp()
        FROM best WHERE rn <= 3"""


def build_all(spark):
    steps = [("name_area_bridge", area_bridge_sql()), ("name_project_bridge", project_bridge_sql()),
             ("developer_name_bridge", developer_bridge_sql()), ("area_crosswalk", crosswalk_sql()),
             ("crosswalk_review", review_sql())]
    for name, sql in steps:
        spark.sql(sql)
        print(f"{name}: rebuilt")