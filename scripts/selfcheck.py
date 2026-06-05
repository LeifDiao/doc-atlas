#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selfcheck.py —— doc-atlas 阶段四自检脚本。

作用：
    用 playwright(同步 API) 无头加载已渲染好的 dashboard.html，
    捕获 console error / pageerror，确认注入数据可被 JSON.parse，
    统计 Mermaid 生成的 <svg> 数、Chart.js 生成的 <canvas> 数、章节 section 数，
    给出结构化自检报告。

运行环境：
    必须用系统 python（playwright 已可 import）：
        /usr/bin/python3 scripts/selfcheck.py DASHBOARD_HTML [--json]

用法（CLI 契约）：
    python3 selfcheck.py DASHBOARD_HTML [--json]
        DASHBOARD_HTML   要校验的单文件 dashboard（绝对/相对路径均可，内部转绝对路径）
        --json           输出机器可读 JSON 报告（json.dumps）；缺省为人类可读文本
    退出码：有错误（ok=False）→ 1；正常 → 0。

如何安装 playwright 浏览器（二选一）：
    1) 安装 playwright 自带 chromium：
           /usr/bin/python3 -m playwright install chromium
       （如缺系统依赖，按官方提示 `playwright install-deps`，macOS 一般不需要。）
    2) 不装 chromium，直接复用系统已装的 Google Chrome：
           本脚本会在 chromium.launch() 失败后自动回退到 launch(channel="chrome")，
           只要 "/Applications/Google Chrome.app" 存在即可。
    若两者都拿不到浏览器，脚本自动降级为“静态模式”：仅对 HTML 文本做基本检查并 warn。
"""

import sys
import os
import re
import json
import argparse


# ── 浏览器内执行的取数/统计脚本（在 page.evaluate 里跑）─────────────────────────
# 取出注入的 dashboard-data 文本，确认能被 JSON.parse；并统计 svg/canvas/section 数。
# 返回一个对象交回 Python 侧汇总。
_BROWSER_PROBE_JS = r"""
() => {
    const out = {
        data_parse_ok: false,       // 注入 JSON 能否 JSON.parse
        data_parse_error: null,     // 解析失败时的错误信息
        has_data_node: false,       // 是否存在 #dashboard-data 容器
        mermaid_svg: 0,             // Mermaid 渲染出的 svg 数
        chart_canvas: 0,            // Chart.js 生成的 canvas 数
        chapter_sections: 0,        // 章节 section 数
        title_text: null            // 页面标题（辅助信息）
    };

    // 1) 注入数据节点 + JSON.parse 验证
    const dataNode = document.getElementById('dashboard-data');
    if (dataNode) {
        out.has_data_node = true;
        try {
            const parsed = JSON.parse(dataNode.textContent);
            out.data_parse_ok = (parsed !== null && typeof parsed === 'object');
            if (parsed && parsed.meta && typeof parsed.meta.title === 'string') {
                out.title_text = parsed.meta.title;
            }
        } catch (e) {
            out.data_parse_ok = false;
            out.data_parse_error = String(e && e.message ? e.message : e);
        }
    }

    // 2) Mermaid 渲染出的 svg：Mermaid 会把代码块替换为内含 svg 的容器。
    //    既统计 .mermaid 容器内的 svg，也统计带 mermaid 标识的 svg，去重计数。
    const svgSet = new Set();
    document.querySelectorAll('.mermaid svg').forEach(s => svgSet.add(s));
    document.querySelectorAll('svg[id^="mermaid"]').forEach(s => svgSet.add(s));
    document.querySelectorAll('svg[aria-roledescription]').forEach(s => svgSet.add(s));
    out.mermaid_svg = svgSet.size;

    // 3) Chart.js 生成的 canvas（Chart.js 始终渲染进 <canvas>）
    out.chart_canvas = document.querySelectorAll('canvas').length;

    // 4) 章节 section：模板里章节区块应带可识别标记。
    //    优先 data-chapter / .chapter；退而求其次统计 <section>。
    let chSections = document.querySelectorAll('section[data-chapter], section.chapter, [data-chapter]').length;
    if (chSections === 0) {
        chSections = document.querySelectorAll('section').length;
    }
    out.chapter_sections = chSections;

    return out;
}
"""


def _build_report():
    """构造一个带默认值的报告骨架。"""
    return {
        "mode": "static",          # "browser" | "static"
        "ok": True,
        "console_errors": [],      # 浏览器 console type=="error" 文本
        "page_errors": [],         # pageerror 异常文本
        "mermaid_svg": 0,
        "chart_canvas": 0,
        "chapter_sections": 0,
        "notes": [],
    }


def _run_browser_check(html_path, report):
    """
    浏览器模式：用 playwright 同步 API 无头加载，捕获错误并统计。
    返回 True 表示成功跑完浏览器流程；返回 False 表示拿不到浏览器，需降级。
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        report["notes"].append(f"playwright 不可导入，降级静态模式：{e}")
        return False

    file_url = "file://" + html_path  # html_path 已是绝对路径

    with sync_playwright() as p:
        browser = None
        launch_err = []

        # 浏览器获取健壮回退：先自带 chromium，失败再用系统 Chrome channel。
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e1:
            launch_err.append(f"chromium.launch 失败：{e1}")
            try:
                browser = p.chromium.launch(headless=True, channel="chrome")
                report["notes"].append("已回退到系统 Chrome（channel=chrome）。")
            except Exception as e2:
                launch_err.append(f"chromium.launch(channel=chrome) 失败：{e2}")
                browser = None

        if browser is None:
            # 两条路都拿不到浏览器 → 交回上层降级静态模式。
            for msg in launch_err:
                report["notes"].append(msg)
            return False

        report["mode"] = "browser"
        try:
            page = browser.new_page()

            # 收集 console error 与 pageerror。
            def _on_console(msg):
                try:
                    if msg.type == "error":
                        report["console_errors"].append(msg.text)
                except Exception:
                    # 个别 playwright 版本属性差异，兜底转字符串。
                    report["console_errors"].append(str(msg))

            def _on_pageerror(err):
                report["page_errors"].append(str(err))

            page.on("console", _on_console)
            page.on("pageerror", _on_pageerror)

            # 加载页面：等到 networkidle（CDN 脚本拉取/解析完成）。
            try:
                page.goto(file_url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                # networkidle 超时不致命（离线可能某 CDN 慢），降级等 load。
                report["notes"].append(f"networkidle 等待异常，改用 load：{e}")
                page.goto(file_url, wait_until="load", timeout=30000)

            # 给 Mermaid / Chart.js 一点渲染时间（它们是异步初始化的）。
            page.wait_for_timeout(2500)

            # 在浏览器里取数 + 统计。
            probe = page.evaluate(_BROWSER_PROBE_JS)

            report["mermaid_svg"] = int(probe.get("mermaid_svg", 0))
            report["chart_canvas"] = int(probe.get("chart_canvas", 0))
            report["chapter_sections"] = int(probe.get("chapter_sections", 0))

            if not probe.get("has_data_node"):
                report["notes"].append("未找到 #dashboard-data 注入容器。")
                report["ok"] = False
            elif not probe.get("data_parse_ok"):
                err = probe.get("data_parse_error")
                report["notes"].append(f"注入数据 JSON.parse 失败：{err}")
                report["ok"] = False
            else:
                report["notes"].append("注入数据 JSON.parse 成功。")

            if probe.get("title_text"):
                report["notes"].append(f"面板标题：{probe['title_text']}")

        finally:
            browser.close()

    return True


def _run_static_check(html_path, report):
    """
    静态模式：拿不到浏览器时的降级检查。
    直接读 HTML 文本，做：
      - 取出 #dashboard-data 的内容并 json.loads；
      - 含关键 section 容器（章节/dashboard 根）；
      - 含 Chart.js / Mermaid 的 CDN 引用。
    静态模式无法真正渲染，故 mermaid_svg/chart_canvas 保持 0，并在 notes 说明。
    """
    report["mode"] = "static"
    report["notes"].append("已降级为静态模式（未启动浏览器，无法真实渲染 svg/canvas）。")

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception as e:
        report["notes"].append(f"读取 HTML 失败：{e}")
        report["ok"] = False
        return

    # 1) 取出注入数据并尝试 json 解析。注入位形如：
    #    <script id="dashboard-data" type="application/json">{...}</script>
    m = re.search(
        r'<script\b[^>]*\bid=["\']dashboard-data["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        report["notes"].append("静态：未找到 #dashboard-data 注入容器。")
        report["ok"] = False
    else:
        raw = m.group(1).strip()
        # renderer 会把 < > & 转成 < > & 防注入，json.loads 能正确还原。
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                report["notes"].append("静态：注入数据可被 json 解析。")
                # 顺带从数据里推断章节数（静态下作为 chapter_sections 的近似）。
                chapters = data.get("chapters")
                if isinstance(chapters, list):
                    report["chapter_sections"] = len(chapters)
                    report["notes"].append(f"静态：model.chapters 含 {len(chapters)} 个章节。")
                title = (data.get("meta") or {}).get("title")
                if title:
                    report["notes"].append(f"静态：面板标题：{title}")
            else:
                report["notes"].append("静态：注入数据解析出来不是对象。")
                report["ok"] = False
        except Exception as e:
            report["notes"].append(f"静态：注入数据 json 解析失败：{e}")
            report["ok"] = False

    # 2) 关键 section 容器存在性（章节根 / dashboard 根）。
    if re.search(r'<section\b', html, re.IGNORECASE) or \
       re.search(r'\bdata-chapter\b', html, re.IGNORECASE) or \
       re.search(r'\bid=["\']dashboard["\']', html, re.IGNORECASE):
        report["notes"].append("静态：检测到关键 section / dashboard 容器。")
    else:
        report["notes"].append("静态：未检测到 section / dashboard 容器（结构可疑）。")

    # 3) Chart.js / Mermaid 的 CDN 引用是否存在（spec 允许的唯一外链）。
    if re.search(r'chart\.js|chart\.umd|cdn[^"\']*chart', html, re.IGNORECASE):
        report["notes"].append("静态：检测到 Chart.js CDN 引用。")
    else:
        report["notes"].append("静态：未检测到 Chart.js CDN 引用。")

    if re.search(r'mermaid', html, re.IGNORECASE):
        report["notes"].append("静态：检测到 Mermaid CDN/脚本引用。")
    else:
        report["notes"].append("静态：未检测到 Mermaid CDN/脚本引用。")


def _finalize_ok(report):
    """
    汇总 ok 判定：
      - 只要有 console error 或 page error → ok=False；
      - 浏览器模式下注入数据解析失败已在流程中置 ok=False；
      - Mermaid/Chart 数为 0 不强制失败（数据可能本就没有图），仅记入 notes。
    """
    if report["console_errors"]:
        report["ok"] = False
    if report["page_errors"]:
        report["ok"] = False

    if report["mode"] == "browser":
        if report["mermaid_svg"] == 0:
            report["notes"].append("提示：未渲染出 Mermaid svg（可能数据里没有图，不计为失败）。")
        if report["chart_canvas"] == 0:
            report["notes"].append("提示：未渲染出 Chart canvas（可能数据里没有图表，不计为失败）。")
        if report["chapter_sections"] == 0:
            report["notes"].append("提示：未检测到章节 section（请确认模板/数据是否含 chapters）。")


def _print_human(report):
    """人类可读打印。"""
    status = "OK" if report["ok"] else "FAILED"
    print("=" * 60)
    print(f"dashboard 自检结果：{status}   （模式：{report['mode']}）")
    print("=" * 60)
    print(f"  Mermaid svg 数      : {report['mermaid_svg']}")
    print(f"  Chart canvas 数     : {report['chart_canvas']}")
    print(f"  章节 section 数     : {report['chapter_sections']}")
    print(f"  console error 数    : {len(report['console_errors'])}")
    print(f"  page error 数       : {len(report['page_errors'])}")

    if report["console_errors"]:
        print("\n  -- console errors --")
        for i, e in enumerate(report["console_errors"], 1):
            print(f"   [{i}] {e}")
    if report["page_errors"]:
        print("\n  -- page errors --")
        for i, e in enumerate(report["page_errors"], 1):
            print(f"   [{i}] {e}")
    if report["notes"]:
        print("\n  -- notes --")
        for n in report["notes"]:
            print(f"   * {n}")
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="阶段四自检：playwright 无头校验 dashboard.html。"
    )
    parser.add_argument("dashboard_html", help="要校验的 dashboard.html 路径")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="输出机器可读 JSON 报告")
    args = parser.parse_args(argv)

    html_path = os.path.abspath(args.dashboard_html)

    report = _build_report()

    if not os.path.isfile(html_path):
        report["ok"] = False
        report["notes"].append(f"文件不存在：{html_path}")
        if args.as_json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            _print_human(report)
        return 1

    # 先尝试浏览器模式，拿不到浏览器再降级静态模式。
    browser_done = False
    try:
        browser_done = _run_browser_check(html_path, report)
    except Exception as e:
        # 浏览器流程中的意外异常：记下来并降级静态，避免自检本身崩掉。
        report["notes"].append(f"浏览器模式异常，降级静态：{e}")
        browser_done = False

    if not browser_done:
        # 重置浏览器模式可能残留的部分状态后做静态检查。
        report["mode"] = "static"
        _run_static_check(html_path, report)

    _finalize_ok(report)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        _print_human(report)

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
