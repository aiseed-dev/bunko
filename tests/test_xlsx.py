"""xlsx（最小xlsx I/O＋表変換）のテスト。"""
from pybunko import xlsx


def test_write_read_roundtrip():
    sheets = {"A": [["h1", "h2"], ["x", "y"], ["", "z"]]}
    data = xlsx.write_workbook(sheets)
    assert xlsx.read_sheet(data) == [["h1", "h2"], ["x", "y"], ["", "z"]]


def test_read_named_sheet_and_names():
    data = xlsx.write_workbook({"項目": [["a"]], "設定": [["k", "v"]]})
    assert xlsx.sheet_names(data) == ["項目", "設定"]
    assert xlsx.read_sheet(data, "設定") == [["k", "v"]]
    assert xlsx.read_sheet(data, "無い") == []


def test_write_escapes_xml_and_unicode():
    data = xlsx.write_workbook({"S": [["<a>&\"'", "日本語"]]})
    assert xlsx.read_sheet(data) == [["<a>&\"'", "日本語"]]


def test_to_markdown_table_escapes_pipe():
    rows = [["品目", "単価"], ["墨|朱", "800"]]
    md = xlsx.to_markdown_table(rows)
    assert "| 墨\\|朱 | 800 |" in md
    assert "| --- | --- |" in md


def test_to_asciidoc_table_header_and_pipe():
    rows = [["品目", "単価"], ["墨|朱", "800"]]
    ad = xlsx.to_asciidoc_table(rows)
    assert '[options="header"]' in ad
    assert "|===" in ad
    assert "|墨\\|朱 |800" in ad


def test_trim_drops_empty_trailing_columns_and_rows():
    rows = [["a", "", ""], ["b", "", ""], ["", "", ""]]
    assert xlsx._trim(rows) == [["a"], ["b"]]


def test_asciidoc_table_renders_in_pyasciidoc():
    import pyasciidoc
    import re
    rows = [["見出し", "数量"], ["紙", "3"], ["墨|朱", "1"]]
    html = pyasciidoc.render(xlsx.to_asciidoc_table(rows))
    assert "<table" in html
    cells = re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)
    assert "墨|朱" in [c.strip() for c in cells]  # パイプ入りセルが割れない
