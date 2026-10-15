from etl.merge_fact import HASH_COLS, COLS, hash_expr, scd1_sql, scd2_sql, BATCHES


def test_place_names_are_not_in_the_hash():
    names = {"area_en", "project_name", "master_project", "building_name",
             "nearest_metro", "nearest_mall", "nearest_landmark"}
    assert not names & set(HASH_COLS)
    assert "area_id" in HASH_COLS and "project_id" in HASH_COLS


def test_nulls_are_hashed_explicitly():
    assert "'<null>'" in hash_expr()


def test_columns_are_unique():
    assert len(COLS) == len(set(COLS))


def test_scd2_closes_and_inserts_in_one_merge():
    sql = scd2_sql()
    assert "CAST(NULL AS STRING) AS merge_key" in sql and "is_current = false" in sql


def test_scd1_only_updates_real_changes():
    assert "f.record_hash <> s.record_hash" in scd1_sql()


def test_batches_go_oldest_first():
    assert BATCHES == ["e1_transactions", "e2_transactions", "transactions_daily"]

from etl.merge_fact import seq


def test_older_batch_never_overwrites_newer():
    assert "WHEN 'e1_transactions' THEN 1" in seq("x")
    assert ">=" in scd1_sql() and ">=" in scd2_sql()