#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_docs.py —— 阶段零：扫描目标文件夹里的候选文档，供「与用户确认」使用。

典型场景：用户打开一个装着若干 PDF/Word/PPT… 的文件夹并运行本 skill，
本脚本递归列出该文件夹里所有可被归一化的文档，让 AI 把清单呈现给用户确认。

用法：
    python3 scan_docs.py [FOLDER] [--json] [--max-depth N]
    - FOLDER 缺省 = 当前工作目录（.）
    - --json     输出机器可读 JSON（否则打印带编号的人类可读清单）
    - --max-depth 限制递归深度（缺省不限制）

只用标准库，用系统 /usr/bin/python3 即可（无需 .venv）。
会跳过：隐藏目录、.venv / node_modules / __pycache__ / doc-atlas-out 等，
以及「本身含 SKILL.md 的目录」（视作 skill 包，不是用户内容）。
"""

import argparse
import json
import os
import sys

# 可被 normalize.py 处理的文档扩展名
DOC_EXTS = {
    "pdf",
    "doc", "docx",
    "ppt", "pptx",
    "xls", "xlsx", "csv",
    "htm", "html",
    "epub",
    "md", "markdown",
    "txt", "rtf",
    "odt", "odp", "ods",
}

# 显式跳过的目录名（外加所有以 . 开头的隐藏目录）
SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "doc-atlas-out", ".idea", ".vscode", "dist", "build", ".cache",
}

TYPE_LABEL = {
    "doc": "docx", "docx": "docx",
    "ppt": "pptx", "pptx": "pptx",
    "xls": "xlsx", "xlsx": "xlsx", "csv": "csv",
    "htm": "html", "html": "html",
    "markdown": "md", "md": "md",
}


def human_size(n):
    """字节数转人类可读。"""
    units = ["B", "KB", "MB", "GB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return ("%d %s" % (int(f), u)) if u == "B" else ("%.1f %s" % (f, u))
        f /= 1024.0
    return str(n)


def ext_of(name):
    return os.path.splitext(name)[1].lower().lstrip(".")


def scan(folder, max_depth=None):
    """递归扫描，返回 [{path(rel), abspath, type, ext, size_bytes}] 按 path 排序。"""
    root = os.path.abspath(folder)
    out = []
    root_depth = root.rstrip(os.sep).count(os.sep)

    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过含 SKILL.md 的目录（skill 包），但允许 root 自身
        if dirpath != root and "SKILL.md" in filenames:
            dirnames[:] = []
            continue

        # 深度限制
        if max_depth is not None:
            depth = dirpath.rstrip(os.sep).count(os.sep) - root_depth
            if depth >= max_depth:
                dirnames[:] = []

        # 过滤子目录：隐藏目录 + 黑名单
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in SKIP_DIRS
        ]

        for fn in filenames:
            if fn.startswith("."):
                continue
            ext = ext_of(fn)
            if ext not in DOC_EXTS:
                continue
            ap = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(ap)
            except OSError:
                size = 0
            out.append({
                "path": os.path.relpath(ap, root),
                "abspath": ap,
                "type": TYPE_LABEL.get(ext, ext),
                "ext": ext,
                "size_bytes": size,
            })

    out.sort(key=lambda r: r["path"].lower())
    return out, root


def main():
    ap = argparse.ArgumentParser(description="扫描目标文件夹里的候选文档")
    ap.add_argument("folder", nargs="?", default=".", help="目标文件夹（缺省=当前目录）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--max-depth", type=int, default=None, help="递归最大深度")
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        print("[scan_docs] 错误：不是有效目录：%s" % args.folder, file=sys.stderr)
        sys.exit(2)

    rows, root = scan(args.folder, args.max_depth)

    if args.json:
        print(json.dumps({"folder": root, "count": len(rows), "files": rows},
                         ensure_ascii=False, indent=2))
        return

    # 人类可读清单
    print("扫描目录：%s" % root)
    if not rows:
        print("未发现可处理的文档（支持：%s）。" % ", ".join(sorted(DOC_EXTS)))
        return
    print("发现 %d 个候选文档：\n" % len(rows))
    width = max(len(r["path"]) for r in rows)
    for i, r in enumerate(rows, 1):
        print("  %2d. %-*s  [%s]  %s" % (i, width, r["path"], r["type"], human_size(r["size_bytes"])))
    print("\n请与用户确认：以上哪些需要纳入梳理整合？是否有遗漏或需排除的？")


if __name__ == "__main__":
    main()
