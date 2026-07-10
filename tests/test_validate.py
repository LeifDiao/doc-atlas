# -*- coding: utf-8 -*-
"""validate_model.py 单测：合法样例全绿 + 各类注入错误全部拦截（stdlib + pytest）。"""
import copy
import json
import os

import pytest

import validate_model as vm

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_MODEL = os.path.join(SKILL_DIR, "examples", "example-model.json")


@pytest.fixture()
def model():
    with open(EXAMPLE_MODEL, encoding="utf-8") as f:
        return json.load(f)


def test_example_model_passes(model):
    rep = vm.validate(model)
    assert rep.errors == []
    assert rep.threshold == []
    assert rep.exit_code == 0


def test_dangling_quote_id(model):
    m = copy.deepcopy(model)
    for ch in m["chapters"]:
        for b in ch["blocks"]:
            if b.get("quote_id"):
                b["quote_id"] = "q999"
    rep = vm.validate(m)
    assert rep.exit_code == 2
    assert any("q999" in e for e in rep.errors)


def test_outline_chapter_mismatch(model):
    m = copy.deepcopy(model)
    m["outline"].append({"id": "9", "title": "幽灵章", "importance": "low", "sources": []})
    rep = vm.validate(m)
    assert rep.exit_code == 2
    assert any("'9'" in e for e in rep.errors)


def test_bad_importance_enum(model):
    m = copy.deepcopy(model)
    m["keypoints"][0]["importance"] = "critical"
    rep = vm.validate(m)
    assert rep.exit_code == 2


def test_dangling_file_id(model):
    m = copy.deepcopy(model)
    m["keypoints"][0]["sources"][0]["file_id"] = "f99"
    rep = vm.validate(m)
    assert rep.exit_code == 2
    assert any("f99" in e for e in rep.errors)


def test_unknown_field_rejected(model):
    m = copy.deepcopy(model)
    m["meta"]["typo_field"] = 1
    rep = vm.validate(m)
    assert rep.exit_code == 2


def test_missing_required_top_key(model):
    m = copy.deepcopy(model)
    del m["outline"]
    rep = vm.validate(m)
    assert rep.exit_code == 2


def test_todo_ratio_threshold(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["todo_count"] = 6      # 6/30 = 20% > 10%
    rep = vm.validate(m)
    assert rep.exit_code == 1
    assert rep.errors == []
    assert rep.threshold


def test_section_coverage_threshold(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["sections_mapped"] = 1
    rep = vm.validate(m)
    assert rep.exit_code == 1


def test_compression_out_of_band_only_warns(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["compression_ratio_x"] = 30
    rep = vm.validate(m)
    assert rep.exit_code == 0
    assert any("压缩" in w for w in rep.warnings)


def test_page_out_of_range_with_workspace(model, tmp_path):
    # 造一个 workspace：f1 只有 3 页
    doc = tmp_path / "somedoc"
    doc.mkdir()
    (doc / "meta.json").write_text(json.dumps({
        "file_id": "f1", "file_name": "somedoc.pdf", "pages": 3,
    }), encoding="utf-8")
    m = copy.deepcopy(model)
    m["files"] = [{"id": "f1", "name": "somedoc.pdf", "type": "pdf"}]
    m["outline"] = [{"id": "1", "title": "t", "importance": "high",
                     "sources": [{"file_id": "f1", "page": 99}]}]
    m["chapters"] = [{"id": "1", "title": "t", "importance": "high",
                      "sources": [], "blocks": []}]
    for k in ("keypoints", "conflicts", "quotes", "diagrams", "charts", "highlights"):
        m[k] = []
    m["file_relations"] = None
    rep = vm.validate(m, workspace=str(tmp_path))
    assert rep.exit_code == 2
    assert any("越界" in e for e in rep.errors)


def test_page_in_range_with_workspace(model, tmp_path):
    doc = tmp_path / "somedoc"
    doc.mkdir()
    (doc / "meta.json").write_text(json.dumps({
        "file_id": "f1", "file_name": "somedoc.pdf", "pages": 3,
    }), encoding="utf-8")
    m = copy.deepcopy(model)
    m["files"] = [{"id": "f1", "name": "somedoc.pdf", "type": "pdf"}]
    m["meta"]["stats"] = {"file_count": 1, "total_pages": 3,
                          "total_words": None, "reading_minutes": None}
    m["outline"] = [{"id": "1", "title": "t", "importance": "high",
                     "sources": [{"file_id": "f1", "page": 2}]}]
    m["chapters"] = [{"id": "1", "title": "t", "importance": "high",
                      "sources": [], "blocks": []}]
    for k in ("keypoints", "conflicts", "quotes", "diagrams", "charts", "highlights"):
        m[k] = []
    m["file_relations"] = None
    m["distillation_report"] = None
    rep = vm.validate(m, workspace=str(tmp_path))
    assert rep.errors == []


# ── 新字段：one_liner / reading_goal / fact_check_items ──────────────────
def test_meta_new_fields_accepted(model):
    m = copy.deepcopy(model)
    m["meta"]["one_liner"] = "一句话定论。"
    m["meta"]["reading_goal"] = "评估要不要续约"
    m["meta"]["schema_version"] = 2
    rep = vm.validate(m)
    assert rep.errors == []


def test_fact_check_items_valid(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["fact_check_items"] = [
        {"claim": "全年营收 41.2 亿", "verdict": "ok",
         "source": {"file_id": "f2", "page": 12}, "note": None},
        {"claim": "毛利率 -3pp", "verdict": "error", "source": None,
         "note": "原文为 -2.1pp，已修正"},
    ]
    rep = vm.validate(m)
    assert rep.errors == []


def test_fact_check_items_bad_verdict(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["fact_check_items"] = [
        {"claim": "x", "verdict": "sure"},
    ]
    rep = vm.validate(m)
    assert rep.exit_code == 2


def test_fact_check_items_dangling_file_id(model):
    m = copy.deepcopy(model)
    m["distillation_report"]["fact_check_items"] = [
        {"claim": "x", "verdict": "ok", "source": {"file_id": "f99", "page": 1}},
    ]
    rep = vm.validate(m)
    assert rep.exit_code == 2
    assert any("f99" in e for e in rep.errors)


# ── workspace 对账：自报数字 vs meta.json ground truth ───────────────────
def _ws_two_files(tmp_path, pages1=22, words1=5200, pages2=25, words2=13400):
    for fid, name, pages, words in (
        ("f1", "Q3-云业务复盘.pptx", pages1, words1),
        ("f2", "2024-云业务年度白皮书.pdf", pages2, words2),
    ):
        d = tmp_path / fid
        d.mkdir()
        (d / "meta.json").write_text(json.dumps({
            "file_id": fid, "file_name": name, "pages": pages, "words": words,
        }), encoding="utf-8")


def test_reconcile_pages_mismatch_is_error(model, tmp_path):
    _ws_two_files(tmp_path)
    m = copy.deepcopy(model)
    m["files"][0]["pages"] = 99          # 自报页数与 meta.json 不符
    rep = vm.validate(m, workspace=str(tmp_path))
    assert rep.exit_code == 2
    assert any("meta.json 不一致" in e for e in rep.errors)


def test_reconcile_total_pages_mismatch_is_error(model, tmp_path):
    _ws_two_files(tmp_path)
    m = copy.deepcopy(model)
    m["meta"]["stats"]["total_pages"] = 99
    rep = vm.validate(m, workspace=str(tmp_path))
    assert rep.exit_code == 2
    assert any("total_pages" in e for e in rep.errors)


def test_reconcile_source_words_deviation_warns(model, tmp_path):
    _ws_two_files(tmp_path)
    m = copy.deepcopy(model)
    m["distillation_report"]["source_words"] = 99999   # 偏差远超容差
    rep = vm.validate(m, workspace=str(tmp_path))
    assert rep.errors == []
    assert any("source_words" in w for w in rep.warnings)


def test_reconcile_consistent_model_passes(model, tmp_path):
    _ws_two_files(tmp_path)
    rep = vm.validate(model, workspace=str(tmp_path))
    assert rep.errors == []
    assert rep.threshold == []
