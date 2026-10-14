from etl.resolve_area import norm, clean_id, RUNGS, crosswalk_sql


def test_names_are_normalised_the_same_way():
    s = norm("x")
    assert "upper(" in s and "trim(x)" in s and "' +'" in s


def test_ladder_has_five_rungs_in_order():
    assert list(RUNGS) == [1, 2, 3, 4, 5]


def test_unmatched_rows_are_kept_not_dropped():
    sql = crosswalk_sql()
    assert "LEFT JOIN" in sql and "-2" in sql and "-1" in sql


def test_ids_lose_trailing_zero():
    assert "[.]0+$" in clean_id("area_id")