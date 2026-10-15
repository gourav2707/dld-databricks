from checks.check_reconcile import series_sql, SEGMENTS


def test_uses_median_never_average():
    sql = series_sql()
    assert "median(amount)" in sql and "avg(" not in sql.lower()


def test_three_segments():
    assert set(SEGMENTS) == {"all", "flat", "villa"}

from checks.check_reconcile import GRAINS


def test_three_grains_each_from_rows():
    assert set(GRAINS) == {"monthly", "quarterly", "yearly"}
    for g in GRAINS:
        assert "median(amount)" in series_sql(g)