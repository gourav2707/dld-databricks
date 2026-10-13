from etl.registry import match_table, part_no, missing_parts


def test_files_map_to_the_right_table():
    assert match_table("extract-1/Buildings.csv") == ("e1_buildings", "csv")
    assert match_table("extract-2/transactions_2026-08-21_18-30-31_0002.csv") == ("e2_transactions", "csv")
    assert match_table("extract-2/projects_2026-07-06_16-25-21_0001 (1).xlsx") == ("e2_projects", "xlsx")
    assert match_table("extract-1/README.txt") == (None, None)


def test_part_number_is_read_from_the_name():
    assert part_no("transactions_2026-08-21_18-30-31_0002.csv") == 2
    assert part_no("projects_2026-07-06_16-25-21_0001 (1).xlsx") == 1
    assert part_no("Buildings.csv") is None


def test_part_1_is_refused_without_part_2():
    assert missing_parts("e2_transactions", [1]) == [2]
    assert missing_parts("e2_transactions", [1, 2]) == []
    assert missing_parts("e1_buildings", [None]) == []