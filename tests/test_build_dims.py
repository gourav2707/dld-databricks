from etl.build_dims import col_expr, special_row, DIMS


def test_blanks_become_null_and_ids_drop_trailing_zero():
    assert col_expr("x", "STRING") == "nullif(trim(`x`), '')"
    assert "[.]0+$" in col_expr("x", "BIGINT")
    assert col_expr(None, "BIGINT") == "CAST(NULL AS BIGINT)"


def test_every_dimension_is_well_formed():
    for name, d in DIMS.items():
        cols = [c for c, _ in d["columns"]]
        assert d["key"] in cols and d["label"] in cols, name
        for table, mapping in d["sources"]:
            assert set(mapping) <= set(cols), f"{name}/{table}"
        assert "'Unknown'" in special_row(d, -1, "Unknown")
        assert "'Not matched'" in special_row(d, -2, "Not matched")