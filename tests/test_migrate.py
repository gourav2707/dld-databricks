from etl.migrate import file_hash, split_sql


def test_hash_changes_when_text_changes():
    assert file_hash("CREATE SCHEMA a;") != file_hash("CREATE SCHEMA a; ")


def test_split_ignores_comments_and_blank_parts():
    sql = "-- note\nCREATE SCHEMA a;\n\nCREATE SCHEMA b;\n"
    assert split_sql(sql) == ["CREATE SCHEMA a", "CREATE SCHEMA b"]


from etl.migrate import selected


def test_upto_applies_only_earlier_migrations():
    names = ["101_crosswalk.sql", "001_schemas.sql", "004_meta.sql", "005_ingest.sql"]
    assert selected(names, "004") == ["001_schemas.sql", "004_meta.sql"]
    assert selected(names) == sorted(names)