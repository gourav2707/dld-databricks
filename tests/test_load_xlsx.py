from etl.load_csv import clean
from etl.load_xlsx import q


def test_column_names_are_cleaned():
    assert clean("Area Name (En)") == "area_name_en"


def test_names_are_quoted_safely():
    assert q("a`b") == "`a``b`"
    

from etl.load_xlsx import strict_to_transitional_xml


def test_strict_excel_names_are_rewritten():
    strict = b'<workbook xmlns="http://purl.oclc.org/ooxml/spreadsheetml/main" conformance="strict"/>'
    assert strict_to_transitional_xml(strict) == \
        b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'