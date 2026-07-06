# -*- coding: utf-8 -*-
"""normalize.py 纯函数单测（不依赖 markitdown / fitz，stdlib + pytest 即可跑）。"""
import os

import normalize as nz


# ── safe_name ──────────────────────────────────────────────────────────
def test_safe_name_strips_illegal_chars():
    # 路径前缀被 basename 去掉，非法字符替换为 _
    assert nz.safe_name('a/b\\c:d*e?f"g<h>i|j.pdf') == "b_c_d_e_f_g_h_i_j"


def test_safe_name_cjk_and_spaces():
    assert nz.safe_name("年度 报告 2024.pdf") == "年度_报告_2024"


def test_safe_name_empty_falls_back():
    assert nz.safe_name("???.pdf") == "document"


def test_safe_name_length_capped():
    assert len(nz.safe_name("x" * 300 + ".pdf")) <= 120


# ── count_words / visible_char_count ───────────────────────────────────
def test_count_words_mixed_cjk_latin():
    # 4 个汉字 + 2 个英文词 + 1 个数字串
    assert nz.count_words("测试文本 hello world 123") == 4 + 3


def test_count_words_empty():
    assert nz.count_words("") == 0
    assert nz.count_words(None) == 0


def test_visible_char_count_ignores_whitespace():
    assert nz.visible_char_count(" a\n b\t c ") == 3


# ── parse_headings ─────────────────────────────────────────────────────
def test_parse_headings_basic_and_fence_skip():
    md = "# 一级\n\n```\n# 代码里的不算\n```\n\n## 二级 **强调**\n"
    hs = nz.parse_headings(md)
    assert [(h["level"], h["title"]) for h in hs] == [(1, "一级"), (2, "二级 强调")]


# ── guess_date（返回 (date, source)）──────────────────────────────────
def test_guess_date_from_content(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("报告日期：2024年3月15日", encoding="utf-8")
    date, source = nz.guess_date("报告日期：2024年3月15日", str(f))
    assert date == "2024-03-15"
    assert source == "content"


def test_guess_date_mtime_fallback(tmp_path):
    f = tmp_path / "d.txt"
    f.write_text("没有日期的正文", encoding="utf-8")
    date, source = nz.guess_date("没有日期的正文", str(f))
    assert source == "mtime"
    assert date is not None


# ── 表格转 Markdown ────────────────────────────────────────────────────
def test_table_rows_to_md_ok():
    rows = [["指标", "数值"], ["营收", "41.2"], ["毛利率", "34%"]]
    md, nrows, ncols, conf = nz._table_rows_to_md(rows)
    assert nrows == 3 and ncols == 2 and conf == "ok"
    assert "| 指标 | 数值 |" in md


def test_table_rows_to_md_rejects_single_column():
    md, _, _, _ = nz._table_rows_to_md([["a"], ["b"]])
    assert md is None


def test_table_rows_to_md_low_confidence_when_sparse():
    rows = [["a", "", ""], ["", "", ""], ["", "", "c"]]
    md, _, _, conf = nz._table_rows_to_md(rows)
    assert conf == "low"


def test_table_rows_to_md_escapes_pipe():
    md, _, _, _ = nz._table_rows_to_md([["k", "v"], ["a|b", "c"], ["d", "e"]])
    assert "a\\|b" in md


# ── 页锚 / page_map ────────────────────────────────────────────────────
def test_build_anchored_markdown_pages_and_offsets():
    md, page_map = nz.build_anchored_markdown(["第一页正文", "", "第三页正文"])
    assert "<!-- [doc-atlas] p.1 -->" in md
    assert "<!-- [doc-atlas] p.3 -->" in md
    assert len(page_map) == 3
    # 空页写占位说明，first_line 为空
    assert page_map[1]["first_line"] == ""
    assert "无文本层" in md
    # char_start 与 md 中锚点位置一致
    for entry in page_map:
        anchor = nz.PAGE_ANCHOR_FMT.format(page=entry["page"])
        assert md.index(anchor) == entry["char_start"]


def test_text_page_ratio():
    long_page = "很" * 30
    assert nz.text_page_ratio([long_page, "", long_page, ""]) == 0.5
    assert nz.text_page_ratio([]) == 0.0
