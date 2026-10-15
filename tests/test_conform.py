from etl.conform import clean, reason_exprs, RAW_COLS, BULK_MAP, DAILY_MAP, TERMS, stg_columns


def test_none_words_become_null():
    s = clean("x")
    assert "'NONE'" in s and "'NULL'" in s and "''" in s


def test_mappings_only_use_known_columns():
    assert set(BULK_MAP) <= set(RAW_COLS)
    assert set(DAILY_MAP) <= set(RAW_COLS)
    assert set(TERMS) <= set(RAW_COLS)


def test_reason_codes_exist():
    joined = " ".join(reason_exprs())
    for code in ["MISSING_ID", "MISSING_DATE", "BAD_DATE", "BAD_NUMBER:amount"]:
        assert code in joined


def test_staging_columns_have_no_duplicates():
    names = [c for c, _ in stg_columns()]
    assert len(names) == len(set(names))

from etl.conform import to_date


def test_day_first_dates_are_rewritten_before_parsing():
    s = to_date("d")
    assert "'$3-$2-$1'" in s and "AS DATE" in s