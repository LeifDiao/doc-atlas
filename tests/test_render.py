# -*- coding: utf-8 -*-
"""render_dashboard.py 单测 + 集成冒烟（stdlib + pytest）。"""
import json
import os

import pytest

import render_dashboard as rd

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_MODEL = os.path.join(SKILL_DIR, "examples", "example-model.json")
EXAMPLES_DIR = os.path.join(SKILL_DIR, "examples")


# ── _looks_like_local_image ────────────────────────────────────────────
def test_looks_like_local_image():
    assert rd._looks_like_local_image("assets/p1-img1.png")
    assert rd._looks_like_local_image("/abs/path/图.JPG")
    assert not rd._looks_like_local_image("data:image/png;base64,xxx")
    assert not rd._looks_like_local_image("https://x.com/a.png")
    assert not rd._looks_like_local_image("no-extension")
    assert not rd._looks_like_local_image("")
    assert not rd._looks_like_local_image(None)


# ── 序列化转义 ─────────────────────────────────────────────────────────
def test_serialize_escapes_script_close():
    model = {"meta": {"title": "</script><script>alert(1)</script> & <b>"}}
    payload = rd._serialize_and_escape(model)
    assert "</script" not in payload
    assert "<" not in payload and ">" not in payload and "&" not in payload
    # JSON 语义不变（< 等还原）
    assert json.loads(payload)["meta"]["title"] == "</script><script>alert(1)</script> & <b>"


# ── 图片定位 ───────────────────────────────────────────────────────────
def test_resolve_image_path_workspace_relative(tmp_path):
    (tmp_path / "f1" / "assets").mkdir(parents=True)
    img = tmp_path / "f1" / "assets" / "a.png"
    img.write_bytes(b"\x89PNG fake")
    got = rd._resolve_image_path("f1/assets/a.png", str(tmp_path))
    assert got is not None and got.samefile(img)


def test_resolve_image_path_missing(tmp_path):
    assert rd._resolve_image_path("nope/x.png", str(tmp_path)) is None


# ── 通用兜底内嵌：白名单字段才动，正文文本不误伤 ──────────────────────
def test_embedder_whitelist(tmp_path):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG fake")
    model = {
        "chapters": [{"blocks": [
            {"type": "image", "src": "pic.png"},
            {"type": "paragraph", "md": "详见 pic.png"},   # 以 .png 结尾的正文，不能被替换
        ]}],
        "cover": "pic.png",          # 白名单字段 → 替换
        "note": "pic.png",           # 非白名单字段 → 保留原文
    }
    emb = rd._ImageEmbedder(str(tmp_path))
    emb.walk(model)
    blocks = model["chapters"][0]["blocks"]
    assert blocks[0]["src"].startswith("data:image/png;base64,")
    assert blocks[1]["md"] == "详见 pic.png"
    assert model["cover"].startswith("data:")
    assert model["note"] == "pic.png"
    assert emb.embedded >= 1 and emb.missing == 0


# ── 集成冒烟：example → dashboard.html ────────────────────────────────
def _render(tmp_path, *extra):
    out = tmp_path / "dash.html"
    rc = rd.main([EXAMPLE_MODEL, str(out), "--workspace", EXAMPLES_DIR] + list(extra))
    return rc, out


def test_render_example_inline(tmp_path):
    rc, out = _render(tmp_path)
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert 'id="dashboard-data"' in html
    assert "doc-atlas:vendor inline" in html        # 前端库已内联
    assert "cdn.jsdelivr" not in html               # 零外链
    assert "__DASHBOARD_DATA__" not in html         # token 已替换
    assert "__VENDOR_JS__" not in html


def test_render_example_cdn(tmp_path):
    rc, out = _render(tmp_path, "--cdn")
    assert rc == 0
    html = out.read_text(encoding="utf-8")
    assert "doc-atlas:vendor cdn" in html
    assert "cdn.jsdelivr" in html


def test_render_rejects_invalid_model(tmp_path):
    bad = tmp_path / "bad.json"
    model = json.load(open(EXAMPLE_MODEL, encoding="utf-8"))
    model["keypoints"][0]["sources"][0]["file_id"] = "f99"   # 悬空引用
    bad.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "dash.html"
    rc = rd.main([str(bad), str(out), "--workspace", EXAMPLES_DIR])
    assert rc == 2          # 渲染前校验拦截
    assert not out.exists()


def test_render_skip_validate_escape_hatch(tmp_path):
    bad = tmp_path / "bad.json"
    model = json.load(open(EXAMPLE_MODEL, encoding="utf-8"))
    model["keypoints"][0]["sources"][0]["file_id"] = "f99"
    bad.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "dash.html"
    rc = rd.main([str(bad), str(out), "--workspace", EXAMPLES_DIR, "--skip-validate"])
    assert rc == 0 and out.exists()
