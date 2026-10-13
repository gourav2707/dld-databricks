from etl.migrate import file_hash, split_sql


def test_hash_changes_when_text_changes():
    assert file_hash("CREATE SCHEMA a;") != file_hash("CREATE SCHEMA a; ")


def test_split_ignores_comments_and_blank_parts():
    sql = "-- note\nCREATE SCHEMA a;\n\nCREATE SCHEMA b;\n"
    assert split_sql(sql) == ["CREATE SCHEMA a", "CREATE SCHEMA b"]