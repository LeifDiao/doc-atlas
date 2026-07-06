#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_model.py —— 阶段二产物 model.json 的机器校验闸（渲染前强制执行）。

把此前只能靠 AI 自觉的硬约束变成机器闸门，分四层：
  1. 结构校验：必填字段 / 类型 / 枚举 / 未知字段（对齐 schema/model.schema.json，
     纯 stdlib 手写实现，无需安装 jsonschema）。
  2. 交叉引用校验：
     - 每个 SourceRef.file_id 必须命中某个 files[].id；
     - 一级 outline 节点 id 与 chapters[].id 必须一一对应；
     - quote_id / diagram_id / chart_id 必须能解析到全局池；
     - outline / files / chapters 等 id 不得重复。
  3. 溯源核查（给 --workspace 时）：按 files[].id ↔ workspace/*/meta.json 的 file_id
     （退而求其次按文件名）配对，校验所有 SourceRef.page 落在 [1, pages] 内。
  4. 炼化阈值（distillation_report 给了数值字段才执行）：
     - sections_mapped == sections_total（章节覆盖 100%）；
     - claims_with_source_count == claims_total（溯源率 100%）；
     - todo_count / data_points ≤ 10%；
     - compression_ratio_x 落在 ~2–15 之外仅告警（3:1–10:1 为宜）。

用法：
    python3 validate_model.py MODEL_JSON [--workspace DIR] [--json]

退出码：
    0 = 通过（可有告警）
    1 = 炼化阈值未达标（结构合法，但按纪律先别交付；修完再来）
    2 = 结构 / 交叉引用 / 页码越界错误（必须修）

纯标准库，python3.9+ 即可。
"""

import argparse
import json
import os
import sys

IMPORTANCE = {"high", "medium", "low"}
CONFIDENCE = {"high", "medium", "low"}
TONE = {"info", "warn", "success", "danger"}

TOP_KEYS = {
    "meta", "files", "file_relations", "highlights", "distillation_report",
    "conflicts", "keypoints", "diagrams", "charts", "quotes",
    "outline", "chapters",
}
REQUIRED_TOP = ("meta", "files", "outline", "chapters")

DISTILL_KEYS = {
    "source_words", "model_words", "compression_ratio_x", "compression_ratio",
    "sections_total", "sections_mapped", "section_coverage",
    "claims_total", "claims_with_source_count", "claims_with_source",
    "todo_count", "data_points", "todo_ratio",
    "derived_numbers", "unmapped_source_blocks", "fact_check",
}

TODO_RATIO_MAX = 0.10          # todo 占比纪律线
COMPRESSION_SOFT_RANGE = (2.0, 15.0)  # 压缩倍数软区间（出界仅告警）


class Report:
    """收集错误（结构/引用）、阈值违规、告警。"""

    def __init__(self):
        self.errors = []      # 结构/交叉引用/页码 —— 退出码 2
        self.threshold = []   # 炼化阈值未达标 —— 退出码 1
        self.warnings = []    # 不拦截

    def err(self, path, msg):
        self.errors.append("%s: %s" % (path, msg))

    def thr(self, msg):
        self.threshold.append(msg)

    def warn(self, path, msg):
        self.warnings.append("%s: %s" % (path, msg))

    @property
    def exit_code(self):
        if self.errors:
            return 2
        if self.threshold:
            return 1
        return 0


# ─────────────────────────────────────────────────────── 基础类型检查工具 ──

def _is_str(v):
    return isinstance(v, str)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_keys(rep, path, obj, allowed, required):
    """未知字段 + 必填字段检查（对齐 additionalProperties:false）。"""
    for k in obj:
        if k not in allowed:
            rep.err(path, "未知字段 %r（schema additionalProperties:false）" % k)
    for k in required:
        if k not in obj:
            rep.err(path, "缺少必填字段 %r" % k)


def _check_opt_str(rep, path, obj, key):
    if key in obj and obj[key] is not None and not _is_str(obj[key]):
        rep.err("%s.%s" % (path, key), "应为字符串或 null")


def _check_opt_int(rep, path, obj, key):
    if key in obj and obj[key] is not None and not _is_int(obj[key]):
        rep.err("%s.%s" % (path, key), "应为整数或 null")


# ─────────────────────────────────────────────────────────── SourceRef ──

def _check_source_ref(rep, path, ref, refs_out):
    if not isinstance(ref, dict):
        rep.err(path, "SourceRef 应为对象")
        return
    _check_keys(rep, path, ref, {"file_id", "page", "loc"}, ("file_id",))
    fid = ref.get("file_id")
    if not _is_str(fid):
        rep.err(path + ".file_id", "应为字符串")
        fid = None
    page = ref.get("page")
    if page is not None and not _is_int(page):
        rep.err(path + ".page", "应为整数或 null")
        page = None
    _check_opt_str(rep, path, ref, "loc")
    if page is None and not ref.get("loc"):
        rep.warn(path, "page 与 loc 均缺失（已知定位时应至少给一个）")
    if fid is not None:
        refs_out.append((path, fid, page))


def _check_sources(rep, path, obj, refs_out, key="sources"):
    if key not in obj:
        return
    arr = obj[key]
    if not isinstance(arr, list):
        rep.err("%s.%s" % (path, key), "应为数组")
        return
    for i, r in enumerate(arr):
        _check_source_ref(rep, "%s.%s[%d]" % (path, key, i), r, refs_out)


# ────────────────────────────────────────────────────────── 各字段检查 ──

def _check_metric_item(rep, path, m, refs):
    if not isinstance(m, dict):
        rep.err(path, "MetricItem 应为对象")
        return
    _check_keys(rep, path, m, {"value", "label", "sub", "importance", "sources"},
                ("value", "label"))
    for k in ("value", "label"):
        if k in m and not _is_str(m[k]):
            rep.err("%s.%s" % (path, k), "应为字符串")
    _check_opt_str(rep, path, m, "sub")
    imp = m.get("importance")
    if imp is not None and imp not in IMPORTANCE:
        rep.err(path + ".importance", "非法枚举 %r" % imp)
    _check_sources(rep, path, m, refs)


def _check_meta(rep, meta, refs):
    path = "meta"
    if not isinstance(meta, dict):
        rep.err(path, "应为对象")
        return
    _check_keys(rep, path, meta,
                {"title", "content_lang", "ui_lang", "generated_at", "stats",
                 "executive_summary"},
                ("title", "content_lang", "stats", "executive_summary"))
    for k in ("title", "content_lang"):
        if k in meta and not _is_str(meta[k]):
            rep.err("%s.%s" % (path, k), "应为字符串")
    _check_opt_str(rep, path, meta, "ui_lang")
    _check_opt_str(rep, path, meta, "generated_at")
    stats = meta.get("stats")
    if isinstance(stats, dict):
        _check_keys(rep, path + ".stats", stats,
                    {"file_count", "total_pages", "total_words", "reading_minutes"},
                    ("file_count",))
        if "file_count" in stats and not _is_int(stats["file_count"]):
            rep.err(path + ".stats.file_count", "应为整数")
        for k in ("total_pages", "total_words", "reading_minutes"):
            _check_opt_int(rep, path + ".stats", stats, k)
    elif stats is not None:
        rep.err(path + ".stats", "应为对象")
    es = meta.get("executive_summary")
    if es is not None:
        if not isinstance(es, list) or len(es) < 1:
            rep.err(path + ".executive_summary", "应为非空字符串数组（至少 1 句）")
        else:
            for i, s in enumerate(es):
                if not _is_str(s):
                    rep.err("%s.executive_summary[%d]" % (path, i), "应为字符串")


def _check_files(rep, files, refs):
    ids = []
    if not isinstance(files, list) or len(files) < 1:
        rep.err("files", "应为非空数组")
        return ids
    for i, f in enumerate(files):
        path = "files[%d]" % i
        if not isinstance(f, dict):
            rep.err(path, "应为对象")
            continue
        _check_keys(rep, path, f,
                    {"id", "name", "type", "pages", "words", "date", "role"},
                    ("id", "name", "type"))
        for k in ("id", "name", "type"):
            if k in f and not _is_str(f[k]):
                rep.err("%s.%s" % (path, k), "应为字符串")
        for k in ("pages", "words"):
            _check_opt_int(rep, path, f, k)
        _check_opt_str(rep, path, f, "date")
        _check_opt_str(rep, path, f, "role")
        if _is_str(f.get("id")):
            if f["id"] in ids:
                rep.err(path + ".id", "文件 id 重复：%r" % f["id"])
            ids.append(f["id"])
    return ids


def _check_conflicts(rep, arr, refs):
    if not isinstance(arr, list):
        rep.err("conflicts", "应为数组")
        return
    seen = set()
    for i, c in enumerate(arr):
        path = "conflicts[%d]" % i
        if not isinstance(c, dict):
            rep.err(path, "应为对象")
            continue
        _check_keys(rep, path, c,
                    {"id", "topic", "positions", "resolution", "confidence"},
                    ("id", "topic", "positions"))
        cid = c.get("id")
        if _is_str(cid):
            if cid in seen:
                rep.err(path + ".id", "冲突 id 重复：%r" % cid)
            seen.add(cid)
        pos = c.get("positions")
        if not isinstance(pos, list) or len(pos) < 2:
            rep.err(path + ".positions", "至少要有 2 个出处不同的说法")
        else:
            for j, p in enumerate(pos):
                ppath = "%s.positions[%d]" % (path, j)
                if not isinstance(p, dict):
                    rep.err(ppath, "应为对象")
                    continue
                _check_keys(rep, ppath, p, {"value", "source"}, ("value", "source"))
                if "value" in p and not _is_str(p["value"]):
                    rep.err(ppath + ".value", "应为字符串")
                if "source" in p:
                    _check_source_ref(rep, ppath + ".source", p["source"], refs)
        _check_opt_str(rep, path, c, "resolution")
        conf = c.get("confidence")
        if conf is not None and conf not in CONFIDENCE:
            rep.err(path + ".confidence", "非法枚举 %r" % conf)


def _check_keypoints(rep, arr, refs):
    if not isinstance(arr, list):
        rep.err("keypoints", "应为数组")
        return
    for i, k in enumerate(arr):
        path = "keypoints[%d]" % i
        if not isinstance(k, dict):
            rep.err(path, "应为对象")
            continue
        _check_keys(rep, path, k, {"id", "text", "kind", "importance", "sources"},
                    ("id", "text", "importance", "sources"))
        for key in ("id", "text"):
            if key in k and not _is_str(k[key]):
                rep.err("%s.%s" % (path, key), "应为字符串")
        _check_opt_str(rep, path, k, "kind")
        if k.get("importance") not in IMPORTANCE:
            rep.err(path + ".importance", "非法枚举 %r" % k.get("importance"))
        _check_sources(rep, path, k, refs)


def _check_chartjs(rep, path, cfg):
    if not isinstance(cfg, dict):
        rep.err(path, "chartjs 应为对象")
        return
    if not _is_str(cfg.get("type")):
        rep.err(path + ".type", "缺少或非法（应为字符串，如 bar/line/pie）")
    if not isinstance(cfg.get("data"), dict):
        rep.err(path + ".data", "缺少或非法（应为对象）")


def _check_pools(rep, model, refs):
    """diagrams / charts / quotes 全局池。返回 (diagram_ids, chart_ids, quote_ids)。"""
    dids, cids, qids = set(), set(), set()
    arr = model.get("diagrams")
    if arr is not None:
        if not isinstance(arr, list):
            rep.err("diagrams", "应为数组")
        else:
            for i, d in enumerate(arr):
                path = "diagrams[%d]" % i
                if not isinstance(d, dict):
                    rep.err(path, "应为对象")
                    continue
                _check_keys(rep, path, d,
                            {"id", "title", "kind", "mermaid", "caption", "sources"},
                            ("id", "title", "mermaid", "sources"))
                for k in ("id", "title", "mermaid"):
                    if k in d and not _is_str(d[k]):
                        rep.err("%s.%s" % (path, k), "应为字符串")
                _check_opt_str(rep, path, d, "kind")
                _check_opt_str(rep, path, d, "caption")
                _check_sources(rep, path, d, refs)
                if _is_str(d.get("id")):
                    if d["id"] in dids:
                        rep.err(path + ".id", "diagram id 重复：%r" % d["id"])
                    dids.add(d["id"])
    arr = model.get("charts")
    if arr is not None:
        if not isinstance(arr, list):
            rep.err("charts", "应为数组")
        else:
            for i, c in enumerate(arr):
                path = "charts[%d]" % i
                if not isinstance(c, dict):
                    rep.err(path, "应为对象")
                    continue
                _check_keys(rep, path, c,
                            {"id", "title", "caption", "chartjs", "sources"},
                            ("id", "title", "chartjs", "sources"))
                for k in ("id", "title"):
                    if k in c and not _is_str(c[k]):
                        rep.err("%s.%s" % (path, k), "应为字符串")
                _check_opt_str(rep, path, c, "caption")
                if "chartjs" in c:
                    _check_chartjs(rep, path + ".chartjs", c["chartjs"])
                _check_sources(rep, path, c, refs)
                if _is_str(c.get("id")):
                    if c["id"] in cids:
                        rep.err(path + ".id", "chart id 重复：%r" % c["id"])
                    cids.add(c["id"])
    arr = model.get("quotes")
    if arr is not None:
        if not isinstance(arr, list):
            rep.err("quotes", "应为数组")
        else:
            for i, q in enumerate(arr):
                path = "quotes[%d]" % i
                if not isinstance(q, dict):
                    rep.err(path, "应为对象")
                    continue
                _check_keys(rep, path, q, {"id", "text", "attribution", "source"},
                            ("id", "text", "source"))
                for k in ("id", "text"):
                    if k in q and not _is_str(q[k]):
                        rep.err("%s.%s" % (path, k), "应为字符串")
                _check_opt_str(rep, path, q, "attribution")
                if "source" in q:
                    _check_source_ref(rep, path + ".source", q["source"], refs)
                if _is_str(q.get("id")):
                    if q["id"] in qids:
                        rep.err(path + ".id", "quote id 重复：%r" % q["id"])
                    qids.add(q["id"])
    return dids, cids, qids


def _check_outline(rep, outline, refs):
    """递归校验 outline，返回 (一级 id 列表, 全部 id 集合)。"""
    top_ids = []
    all_ids = set()

    def walk(nodes, path):
        if not isinstance(nodes, list):
            rep.err(path, "应为数组")
            return
        for i, n in enumerate(nodes):
            npath = "%s[%d]" % (path, i)
            if not isinstance(n, dict):
                rep.err(npath, "应为对象")
                continue
            _check_keys(rep, npath, n,
                        {"id", "title", "summary", "importance", "sources", "children"},
                        ("id", "title", "importance", "sources"))
            nid = n.get("id")
            for k in ("id", "title"):
                if k in n and not _is_str(n[k]):
                    rep.err("%s.%s" % (npath, k), "应为字符串")
            _check_opt_str(rep, npath, n, "summary")
            if n.get("importance") not in IMPORTANCE:
                rep.err(npath + ".importance", "非法枚举 %r" % n.get("importance"))
            _check_sources(rep, npath, n, refs)
            if _is_str(nid):
                if nid in all_ids:
                    rep.err(npath + ".id", "outline id 重复：%r" % nid)
                all_ids.add(nid)
                if path == "outline":
                    top_ids.append(nid)
            if "children" in n:
                walk(n["children"], npath + ".children")

    walk(outline, "outline")
    return top_ids, all_ids


BLOCK_SPECS = {
    # type: (allowed_keys, required_keys)
    "paragraph": ({"type", "md", "sources"}, ("md",)),
    "callout": ({"type", "tone", "title", "md", "sources"}, ("tone", "md")),
    "keypoints": ({"type", "items"}, ("items",)),
    "metric": ({"type", "title", "items", "sources"}, ("items",)),
    "table": ({"type", "title", "columns", "rows", "sources"}, ("columns", "rows")),
    "image": ({"type", "src", "caption", "source"}, ("src",)),
    "subsections": ({"type", "items"}, ("items",)),
}


def _check_block(rep, path, b, refs, pools):
    dids, cids, qids = pools
    if not isinstance(b, dict):
        rep.err(path, "block 应为对象")
        return
    btype = b.get("type")
    if btype == "quote":
        if "quote_id" in b:
            _check_keys(rep, path, b, {"type", "quote_id"}, ("quote_id",))
            if not _is_str(b.get("quote_id")):
                rep.err(path + ".quote_id", "应为字符串")
            elif b["quote_id"] not in qids:
                rep.err(path + ".quote_id", "引用不存在的金句 %r" % b["quote_id"])
        else:
            _check_keys(rep, path, b, {"type", "text", "attribution", "source"},
                        ("text",))
            if "text" in b and not _is_str(b["text"]):
                rep.err(path + ".text", "应为字符串")
            if "source" in b:
                _check_source_ref(rep, path + ".source", b["source"], refs)
        return
    if btype == "diagram":
        if "diagram_id" in b:
            _check_keys(rep, path, b, {"type", "diagram_id"}, ("diagram_id",))
            if not _is_str(b.get("diagram_id")):
                rep.err(path + ".diagram_id", "应为字符串")
            elif b["diagram_id"] not in dids:
                rep.err(path + ".diagram_id", "引用不存在的关系图 %r" % b["diagram_id"])
        else:
            _check_keys(rep, path, b, {"type", "title", "mermaid", "caption", "sources"},
                        ("mermaid",))
            if "mermaid" in b and not _is_str(b["mermaid"]):
                rep.err(path + ".mermaid", "应为字符串")
            _check_sources(rep, path, b, refs)
        return
    if btype == "chart":
        if "chart_id" in b:
            _check_keys(rep, path, b, {"type", "chart_id"}, ("chart_id",))
            if not _is_str(b.get("chart_id")):
                rep.err(path + ".chart_id", "应为字符串")
            elif b["chart_id"] not in cids:
                rep.err(path + ".chart_id", "引用不存在的图表 %r" % b["chart_id"])
        else:
            _check_keys(rep, path, b, {"type", "title", "chartjs", "caption", "sources"},
                        ("chartjs",))
            if "chartjs" in b:
                _check_chartjs(rep, path + ".chartjs", b["chartjs"])
            _check_sources(rep, path, b, refs)
        return
    spec = BLOCK_SPECS.get(btype)
    if spec is None:
        rep.err(path, "未知 block 类型 %r" % btype)
        return
    allowed, required = spec
    _check_keys(rep, path, b, allowed, required)
    if btype == "callout" and b.get("tone") not in TONE:
        rep.err(path + ".tone", "非法枚举 %r" % b.get("tone"))
    if btype == "paragraph" and "md" in b and not _is_str(b["md"]):
        rep.err(path + ".md", "应为字符串")
    if btype == "keypoints":
        for j, it in enumerate(b.get("items") or []):
            ipath = "%s.items[%d]" % (path, j)
            if not isinstance(it, dict):
                rep.err(ipath, "应为对象")
                continue
            _check_keys(rep, ipath, it, {"text", "importance", "sources"},
                        ("text", "importance"))
            if it.get("importance") not in IMPORTANCE:
                rep.err(ipath + ".importance", "非法枚举 %r" % it.get("importance"))
            _check_sources(rep, ipath, it, refs)
    if btype == "metric":
        items = b.get("items")
        if not isinstance(items, list) or len(items) < 1:
            rep.err(path + ".items", "应为非空数组")
        else:
            for j, it in enumerate(items):
                _check_metric_item(rep, "%s.items[%d]" % (path, j), it, refs)
        _check_sources(rep, path, b, refs)
    if btype == "table":
        cols = b.get("columns")
        rows = b.get("rows")
        if not isinstance(cols, list):
            rep.err(path + ".columns", "应为数组")
        if not isinstance(rows, list):
            rep.err(path + ".rows", "应为数组")
        else:
            for j, r in enumerate(rows):
                if not isinstance(r, list):
                    rep.err("%s.rows[%d]" % (path, j), "应为数组")
                    continue
                for k, cell in enumerate(r):
                    if not (_is_str(cell) or _is_num(cell)):
                        rep.err("%s.rows[%d][%d]" % (path, j, k),
                                "单元格应为字符串或数字")
        _check_sources(rep, path, b, refs)
    if btype == "image":
        if "src" in b and not _is_str(b["src"]):
            rep.err(path + ".src", "应为字符串")
        if "source" in b:
            _check_source_ref(rep, path + ".source", b["source"], refs)
    if btype == "subsections":
        for j, it in enumerate(b.get("items") or []):
            ipath = "%s.items[%d]" % (path, j)
            if not isinstance(it, dict):
                rep.err(ipath, "应为对象")
                continue
            _check_keys(rep, ipath, it,
                        {"id", "title", "summary", "importance", "sources"},
                        ("id", "title", "summary", "importance", "sources"))
            if it.get("importance") not in IMPORTANCE:
                rep.err(ipath + ".importance", "非法枚举 %r" % it.get("importance"))
            _check_sources(rep, ipath, it, refs)


def _check_chapters(rep, chapters, refs, pools):
    ids = []
    if not isinstance(chapters, list) or len(chapters) < 1:
        rep.err("chapters", "应为非空数组")
        return ids
    for i, ch in enumerate(chapters):
        path = "chapters[%d]" % i
        if not isinstance(ch, dict):
            rep.err(path, "应为对象")
            continue
        _check_keys(rep, path, ch,
                    {"id", "title", "importance", "sources", "blocks"},
                    ("id", "title", "importance", "sources", "blocks"))
        for k in ("id", "title"):
            if k in ch and not _is_str(ch[k]):
                rep.err("%s.%s" % (path, k), "应为字符串")
        if ch.get("importance") not in IMPORTANCE:
            rep.err(path + ".importance", "非法枚举 %r" % ch.get("importance"))
        _check_sources(rep, path, ch, refs)
        blocks = ch.get("blocks")
        if isinstance(blocks, list):
            for j, b in enumerate(blocks):
                _check_block(rep, "%s.blocks[%d]" % (path, j), b, refs, pools)
        elif blocks is not None:
            rep.err(path + ".blocks", "应为数组")
        if _is_str(ch.get("id")):
            if ch["id"] in ids:
                rep.err(path + ".id", "章节 id 重复：%r" % ch["id"])
            ids.append(ch["id"])
    return ids


def _check_distillation(rep, d):
    if d is None:
        return
    path = "distillation_report"
    if not isinstance(d, dict):
        rep.err(path, "应为对象或 null")
        return
    _check_keys(rep, path, d, DISTILL_KEYS, ())
    for k in ("source_words", "model_words", "sections_total", "sections_mapped",
              "claims_total", "claims_with_source_count", "todo_count",
              "data_points", "derived_numbers"):
        _check_opt_int(rep, path, d, k)
    for k in ("compression_ratio", "section_coverage", "claims_with_source",
              "todo_ratio", "fact_check"):
        _check_opt_str(rep, path, d, k)
    if ("compression_ratio_x" in d and d["compression_ratio_x"] is not None
            and not _is_num(d["compression_ratio_x"])):
        rep.err(path + ".compression_ratio_x", "应为数字或 null")
    usb = d.get("unmapped_source_blocks")
    if usb is not None and not isinstance(usb, list):
        rep.err(path + ".unmapped_source_blocks", "应为数组")

    # ── 炼化阈值（只在数值字段齐备时执行）──
    st, sm = d.get("sections_total"), d.get("sections_mapped")
    if _is_int(st) and _is_int(sm) and sm < st:
        rep.thr("章节覆盖率 %d/%d < 100%%：有源章节未映射到 outline，回去补齐再交付" % (sm, st))
    ct, cs = d.get("claims_total"), d.get("claims_with_source_count")
    if _is_int(ct) and _is_int(cs) and cs < ct:
        rep.thr("溯源率 %d/%d < 100%%：存在无源声明，补源或删除" % (cs, ct))
    tc, dp = d.get("todo_count"), d.get("data_points")
    if _is_int(tc) and _is_int(dp) and dp > 0 and tc / dp > TODO_RATIO_MAX:
        rep.thr("待核实占比 %d/%d ≈ %.0f%% > %.0f%%：多半是表格数值列没抽好，"
                "先回查原件补回真值再交付"
                % (tc, dp, 100.0 * tc / dp, 100 * TODO_RATIO_MAX))
    cx = d.get("compression_ratio_x")
    if _is_num(cx) and not (COMPRESSION_SOFT_RANGE[0] <= cx <= COMPRESSION_SOFT_RANGE[1]):
        rep.warn(path + ".compression_ratio_x",
                 "压缩倍数 %.1f 落在 %g–%g 之外（~3–10 为宜；过低疑似搬运、过高疑似漏收）"
                 % (cx, COMPRESSION_SOFT_RANGE[0], COMPRESSION_SOFT_RANGE[1]))
    # 数值字段完全缺失时提示（阈值无法机器执行）
    if not any(_is_int(d.get(k)) for k in
               ("sections_total", "claims_total", "todo_count")):
        rep.warn(path, "未提供数值字段（sections_*/claims_*/todo_count 等），"
                       "炼化阈值无法机器校验，仅能靠展示文案自觉")


# ─────────────────────────────────────────────────────── workspace 页码核查 ──

def _load_workspace_pages(workspace):
    """
    扫描 workspace/*/meta.json，返回两张映射：
      by_id   : meta.file_id → pages(int|None)
      by_name : meta.file_name → pages(int|None)
    """
    by_id, by_name = {}, {}
    if not workspace or not os.path.isdir(workspace):
        return by_id, by_name
    for entry in sorted(os.listdir(workspace)):
        mp = os.path.join(workspace, entry, "meta.json")
        if not os.path.isfile(mp):
            continue
        try:
            with open(mp, "r", encoding="utf-8") as f:
                m = json.load(f)
        except Exception:  # noqa: BLE001
            continue
        pages = m.get("pages")
        if not isinstance(pages, int):
            pages = None
        if isinstance(m.get("file_id"), str):
            by_id[m["file_id"]] = pages
        if isinstance(m.get("file_name"), str):
            by_name[m["file_name"]] = pages
    return by_id, by_name


def _check_pages_against_workspace(rep, model, refs, workspace):
    by_id, by_name = _load_workspace_pages(workspace)
    if not by_id and not by_name:
        rep.warn("workspace", "未在 %r 找到任何 meta.json，跳过页码越界核查" % workspace)
        return
    # files[].id → pages（先按 meta.file_id 配，再按文件名兜底）
    pages_of = {}
    for f in model.get("files") or []:
        if not isinstance(f, dict) or not _is_str(f.get("id")):
            continue
        fid = f["id"]
        if fid in by_id:
            pages_of[fid] = by_id[fid]
        elif _is_str(f.get("name")) and f["name"] in by_name:
            pages_of[fid] = by_name[f["name"]]
        else:
            rep.warn("files", "文件 %r 在 workspace 里找不到对应 meta.json"
                              "（归一化时用 --file-id %s 可对齐），跳过其页码核查"
                     % (fid, fid))
    for path, fid, page in refs:
        if page is None or fid not in pages_of:
            continue
        pages = pages_of[fid]
        if pages is None:
            continue
        if page < 1 or page > pages:
            rep.err(path, "页码越界：p.%d 超出文件 %r 的范围 [1, %d]"
                    % (page, fid, pages))


# ──────────────────────────────────────────────────────────────── 主流程 ──

def validate(model, workspace=None):
    rep = Report()
    refs = []  # [(path, file_id, page|None)]

    if not isinstance(model, dict):
        rep.err("$", "顶层必须是对象")
        return rep

    _check_keys(rep, "$", model, TOP_KEYS, REQUIRED_TOP)

    if isinstance(model.get("meta"), dict) or model.get("meta") is not None:
        _check_meta(rep, model.get("meta"), refs)
    file_ids = _check_files(rep, model.get("files"), refs)

    fr = model.get("file_relations")
    if fr is not None:
        if not isinstance(fr, dict):
            rep.err("file_relations", "应为对象或 null")
        else:
            _check_keys(rep, "file_relations", fr, {"mermaid", "note"}, ("mermaid",))
            if "mermaid" in fr and not _is_str(fr["mermaid"]):
                rep.err("file_relations.mermaid", "应为字符串")
            _check_opt_str(rep, "file_relations", fr, "note")

    hl = model.get("highlights")
    if hl is not None:
        if not isinstance(hl, list):
            rep.err("highlights", "应为数组")
        else:
            for i, m in enumerate(hl):
                _check_metric_item(rep, "highlights[%d]" % i, m, refs)

    if model.get("conflicts") is not None:
        _check_conflicts(rep, model["conflicts"], refs)
    if model.get("keypoints") is not None:
        _check_keypoints(rep, model["keypoints"], refs)

    pools = _check_pools(rep, model, refs)

    top_outline_ids, _all_outline_ids = ([], set())
    if model.get("outline") is not None:
        top_outline_ids, _all_outline_ids = _check_outline(rep, model["outline"], refs)
    chapter_ids = []
    if model.get("chapters") is not None:
        chapter_ids = _check_chapters(rep, model["chapters"], refs, pools)

    # 一级 outline ↔ chapters 一一对应
    so, sc = set(top_outline_ids), set(chapter_ids)
    for missing in sorted(so - sc):
        rep.err("chapters", "一级 outline 节点 %r 没有对应章节（id 需一致）" % missing)
    for extra in sorted(sc - so):
        rep.err("chapters", "章节 %r 没有对应的一级 outline 节点" % extra)

    # SourceRef.file_id 全部命中 files[].id
    fid_set = set(file_ids)
    for path, fid, _page in refs:
        if fid not in fid_set:
            rep.err(path, "file_id %r 不在 files[].id 中" % fid)

    _check_distillation(rep, model.get("distillation_report"))

    if workspace:
        _check_pages_against_workspace(rep, model, refs, workspace)

    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="model.json 机器校验：结构 / 交叉引用 / 页码越界 / 炼化阈值")
    ap.add_argument("model_json", help="model.json 路径")
    ap.add_argument("--workspace", default=None,
                    help="workspace 根目录（给了才做 SourceRef 页码越界核查）")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="输出机器可读 JSON 报告")
    args = ap.parse_args(argv)

    try:
        with open(args.model_json, "r", encoding="utf-8") as f:
            model = json.load(f)
    except FileNotFoundError:
        print("[validate] 错误：文件不存在：%s" % args.model_json, file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print("[validate] 错误：不是合法 JSON：%s" % e, file=sys.stderr)
        return 2

    rep = validate(model, workspace=args.workspace)

    if args.as_json:
        print(json.dumps({
            "ok": rep.exit_code == 0,
            "exit_code": rep.exit_code,
            "errors": rep.errors,
            "threshold_violations": rep.threshold,
            "warnings": rep.warnings,
        }, ensure_ascii=False, indent=2))
        return rep.exit_code

    status = {0: "通过 ✓", 1: "阈值未达标（先别交付）", 2: "未通过 ✗"}[rep.exit_code]
    print("=" * 60)
    print("model.json 校验结果：%s" % status)
    print("  错误 %d · 阈值违规 %d · 告警 %d"
          % (len(rep.errors), len(rep.threshold), len(rep.warnings)))
    print("=" * 60)
    if rep.errors:
        print("\n-- 错误（必须修，退出码 2）--")
        for e in rep.errors:
            print("  ✗ %s" % e)
    if rep.threshold:
        print("\n-- 炼化阈值（按纪律先别交付，退出码 1）--")
        for t in rep.threshold:
            print("  ⚠ %s" % t)
    if rep.warnings:
        print("\n-- 告警（不拦截）--")
        for w in rep.warnings:
            print("  · %s" % w)
    print()
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
