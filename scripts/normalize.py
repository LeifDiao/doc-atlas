#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize.py —— 阶段一：单个文档归一化为 Markdown 中间层。

把任意支持的格式（pdf/docx/pptx/xlsx/html/epub/md/...）转成统一的
Markdown，并在工作区产出「三件套」：
    WORKSPACE/<安全文件名>/
        ├── content.md     完整 Markdown 正文（不截断）；PDF 表格按行×列结构化抽取后追加在文末
        ├── assets/        仅 PDF：抽取的有信息量图片（p<page>-img<n>.png）
        └── meta.json      文件元信息 + 标题→页码映射 + 资源清单 + 表格登记(tables/table_extraction)

依赖：
    - 标准库
    - markitdown[pdf,docx,pptx,xlsx,xls]  （格式转换；装在 .venv 的 python3.11 里）
    - pymupdf / fitz    （PDF 抽图 + 标题定位页码 + find_tables 表格抽取；缺失则降级跳过）
    可选外部命令：
    - ocrmypdf          （扫描版 PDF 回退 OCR；缺失则仅在 meta 标记 scanned）

用法：
    python normalize.py INPUT_FILE --out WORKSPACE_DIR [--file-id f1]

注意：本脚本必须用 .venv（python3.11）执行，否则 import markitdown 会失败。
先运行 scripts/bootstrap.sh 取得 venv python 路径。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

# ── 抽图过滤阈值（过滤掉装饰性/图标级小图）──────────────────────────
MIN_IMG_WIDTH = 80          # 像素
MIN_IMG_HEIGHT = 80         # 像素
MIN_IMG_AREA = 100 * 100    # 像素面积下限
MIN_IMG_BYTES = 3 * 1024    # 解码后字节下限（再排掉纯色/极小图）

# 扫描版判定：去掉空白后正文字符少于该阈值且是 pdf → 视作扫描版
SCANNED_TEXT_THRESHOLD = 100


# ════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════
def eprint(*args):
    """打印到 stderr。"""
    print(*args, file=sys.stderr)


def safe_name(filename):
    """把文件名（含扩展名）转成安全的目录名：去扩展名、替换非法字符。"""
    base = os.path.basename(filename)
    stem, _ext = os.path.splitext(base)
    # 替换路径分隔符与控制/非法字符；保留中英文、数字、常见连接符
    stem = re.sub(r'[\\/:\*\?"<>\|\x00-\x1f]', "_", stem).strip()
    stem = re.sub(r"\s+", "_", stem)
    stem = stem.strip("._") or "document"
    # 限长，避免超长文件名问题
    return stem[:120]


def detect_file_type(path):
    """根据扩展名给出标准化的文件类型标签。"""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mapping = {
        "pdf": "pdf",
        "doc": "docx", "docx": "docx",
        "ppt": "pptx", "pptx": "pptx",
        "xls": "xlsx", "xlsx": "xlsx", "csv": "csv",
        "htm": "html", "html": "html",
        "epub": "epub",
        "md": "md", "markdown": "md",
        "txt": "txt",
        "json": "json", "xml": "xml",
    }
    return mapping.get(ext, ext or "unknown")


def count_words(text):
    """统计字数：中文按单字计、英文/数字按词计，两者相加。"""
    if not text:
        return 0
    cjk = re.findall(r"[一-鿿㐀-䶿]", text)
    latin = re.findall(r"[A-Za-z0-9]+(?:[\-'][A-Za-z0-9]+)*", text)
    return len(cjk) + len(latin)


def visible_char_count(text):
    """去掉所有空白字符后的可见字符数（用于扫描版判定）。"""
    if not text:
        return 0
    return len(re.sub(r"\s+", "", text))


def guess_date(text, src_path):
    """
    启发式推断文档日期：
      1) 先看文件系统 mtime（兜底）；
      2) 在正文前若干字符里找形如 2023-01-02 / 2023年1月2日 / 2023/1/2 的日期，优先采用。
    返回 ISO 日期字符串（YYYY-MM-DD）或 None。
    """
    candidate = None
    head = (text or "")[:4000]

    patterns = [
        r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",       # 2023-01-02 / 2023/1/2
        r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",  # 2023年1月2日
        r"(20\d{2})\s*年\s*(\d{1,2})\s*月",                  # 2023年1月（无日）
    ]
    for pat in patterns:
        m = re.search(pat, head)
        if m:
            try:
                y = int(m.group(1))
                mo = int(m.group(2)) if m.lastindex and m.lastindex >= 2 else 1
                d = int(m.group(3)) if m.lastindex and m.lastindex >= 3 else 1
                if 1 <= mo <= 12 and 1 <= d <= 31:
                    candidate = f"{y:04d}-{mo:02d}-{d:02d}"
                    break
            except (ValueError, IndexError):
                continue

    if candidate:
        return candidate

    # 兜底：文件 mtime
    try:
        ts = os.path.getmtime(src_path)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except OSError:
        return None


def parse_headings(md_text):
    """
    从 Markdown 抽取标题索引（ATX 风格 # / ## / ...）。
    返回 [{level:int, title:str}]，跳过代码块内的 #。
    """
    headings = []
    in_fence = False
    fence_re = re.compile(r"^\s*(```|~~~)")
    h_re = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
    for line in (md_text or "").splitlines():
        if fence_re.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = h_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            # 去掉标题里残留的 markdown 强调符号
            title = re.sub(r"[*_`]+", "", title).strip()
            if title:
                headings.append({"level": level, "title": title})
    return headings


# ════════════════════════════════════════════════════════════════════
# markitdown 转换
# ════════════════════════════════════════════════════════════════════
def convert_with_markitdown(path):
    """
    用 markitdown 把文件转 Markdown，返回正文字符串。
    import 失败 → 打印指引并以退出码 3 退出。
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        eprint(
            "[normalize] 错误：无法 import markitdown。\n"
            "            请先运行 scripts/bootstrap.sh，并用 .venv 的 python 执行本脚本，例如：\n"
            '            "<SKILL_DIR>/.venv/bin/python" scripts/normalize.py INPUT --out WORKSPACE'
        )
        sys.exit(3)

    md = MarkItDown()
    result = md.convert(path)
    # MarkItDown 结果对象的正文在 text_content
    return result.text_content or ""


# ════════════════════════════════════════════════════════════════════
# PDF 专属：抽图 + 标题定位页码（PyMuPDF / fitz）
# ════════════════════════════════════════════════════════════════════
def _try_import_fitz():
    """尝试导入 fitz；失败返回 None（调用方据此跳过相关功能，不崩）。"""
    try:
        import fitz  # PyMuPDF
        return fitz
    except Exception as e:  # noqa: BLE001 - 任何导入异常都安全降级
        eprint(f"[normalize] 提示：PyMuPDF(fitz) 不可用（{e}），跳过 PDF 抽图与页码定位。")
        return None


def pdf_extract_assets(fitz, pdf_path, assets_dir):
    """
    从 PDF 抽取「有信息量」的图片到 assets_dir。
    过滤极小图标（按尺寸/面积/字节），命名 p<page>-img<n>.png，记录来源页。
    返回 [{path, page}]，path 为相对 meta.json 所在目录的相对路径（assets/xxx.png）。
    """
    assets = []
    seen_xrefs = set()  # 同一 xref 在多页重复出现时只抽一次
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        eprint(f"[normalize] 提示：打开 PDF 抽图失败（{e}），跳过抽图。")
        return assets

    try:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_no = page_index + 1
            try:
                img_list = page.get_images(full=True)
            except Exception:  # noqa: BLE001
                continue

            n_on_page = 0
            for img in img_list:
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                try:
                    info = doc.extract_image(xref)
                except Exception:  # noqa: BLE001
                    continue
                if not info:
                    continue

                width = info.get("width", 0)
                height = info.get("height", 0)
                img_bytes = info.get("image", b"")

                # ── 过滤：尺寸 / 面积 / 字节 ──
                if width < MIN_IMG_WIDTH or height < MIN_IMG_HEIGHT:
                    continue
                if width * height < MIN_IMG_AREA:
                    continue
                if len(img_bytes) < MIN_IMG_BYTES:
                    continue

                seen_xrefs.add(xref)
                n_on_page += 1

                # 统一转 PNG 输出（用 Pixmap 处理各种色彩空间，含 CMYK/带 alpha）
                out_name = f"p{page_no}-img{n_on_page}.png"
                out_path = os.path.join(assets_dir, out_name)
                ok = False
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha >= 4:  # CMYK 等 → 转 RGB
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    pix.save(out_path)
                    pix = None
                    ok = True
                except Exception:  # noqa: BLE001
                    # 兜底：直接写原始字节（按其原扩展名）
                    ext = info.get("ext", "png")
                    out_name = f"p{page_no}-img{n_on_page}.{ext}"
                    out_path = os.path.join(assets_dir, out_name)
                    try:
                        with open(out_path, "wb") as f:
                            f.write(img_bytes)
                        ok = True
                    except OSError:
                        ok = False

                if ok:
                    assets.append({
                        "path": os.path.join("assets", out_name),
                        "page": page_no,
                    })
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass

    return assets


def pdf_locate_heading_pages(fitz, pdf_path, headings):
    """
    用 fitz 逐页搜索每个标题文本，给标题补上页码。
    返回带 page 字段的 heading_index（定位不到则 page=None）。
    为效率：预先缓存每页文本，按标题在全文中做包含匹配，取最早出现页。
    """
    # 先尝试打开并缓存每页文本
    page_texts = []
    try:
        doc = fitz.open(pdf_path)
        for i in range(doc.page_count):
            try:
                page_texts.append(doc.load_page(i).get_text("text") or "")
            except Exception:  # noqa: BLE001
                page_texts.append("")
        doc.close()
    except Exception as e:  # noqa: BLE001
        eprint(f"[normalize] 提示：PDF 页码定位读取失败（{e}），标题页码置空。")
        return [dict(h, page=None) for h in headings]

    # 归一化页文本：去多余空白，便于跨换行匹配标题
    def norm(s):
        return re.sub(r"\s+", "", s)

    norm_pages = [norm(t) for t in page_texts]

    out = []
    for h in headings:
        title = h["title"]
        key = norm(title)
        page = None
        if key:
            for idx, np_text in enumerate(norm_pages):
                if key and key in np_text:
                    page = idx + 1
                    break
        out.append(dict(h, page=page))
    return out


# ════════════════════════════════════════════════════════════════════
# PDF 专属：表格结构化抽取（保数值列）
# ════════════════════════════════════════════════════════════════════
def _table_rows_to_md(rows):
    """
    把 PyMuPDF Table.extract() 的二维数组转成 Markdown 表格。
    返回 (md | None, nrows, ncols, confidence)。
    过滤：行<2 或 列<2 → None（不是有意义的表）。
    置信度：空单元格占比 > 50% 或 数据行过少 → "low"，否则 "ok"。
    """
    if not rows or not isinstance(rows, list):
        return None, 0, 0, "low"
    norm = []
    for r in rows:
        if not isinstance(r, (list, tuple)):
            continue
        norm.append([("" if c is None else str(c)).replace("\r", " ").replace("\n", " ").strip()
                     for c in r])
    if len(norm) < 2:
        return None, 0, 0, "low"
    ncols = max(len(r) for r in norm)
    if ncols < 2:
        return None, 0, 0, "low"
    for r in norm:                       # 补齐参差不齐的列
        if len(r) < ncols:
            r.extend([""] * (ncols - len(r)))

    total = sum(len(r) for r in norm)
    empty = sum(1 for r in norm for c in r if c == "")
    conf = "low" if (total == 0 or empty / total > 0.5 or len(norm) < 3) else "ok"

    def cell(c):
        return c.replace("|", "\\|")

    lines = ["| " + " | ".join(cell(c) for c in norm[0]) + " |",
             "| " + " | ".join(["---"] * ncols) + " |"]
    for r in norm[1:]:
        lines.append("| " + " | ".join(cell(c) for c in r) + " |")
    return "\n".join(lines), len(norm), ncols, conf


def pdf_extract_tables(fitz, pdf_path):
    """
    用 PyMuPDF 的 page.find_tables() 把表格按行×列结构化抽取，补全 markitdown 易丢的数值列。
    返回 (tables_meta, appendix_md, status)：
      tables_meta : [{page, rows, cols, confidence}]   —— 登记进 meta.json，便于阶段二回查
      appendix_md : 追加到 content.md 末尾的 Markdown（无表则 ""）
      status      : "ok" | "low" | "none"（none=是 PDF 但没抽到表）
    find_tables 在旧版 PyMuPDF 可能不存在；任何异常都安全降级。
    """
    tables_meta = []
    md_parts = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        eprint(f"[normalize] 提示：打开 PDF 抽表失败（{e}），跳过表格结构化抽取。")
        return [], "", None

    table_no = 0
    try:
        for i in range(doc.page_count):
            page_no = i + 1
            try:
                page = doc.load_page(i)
                finder = page.find_tables()
            except Exception:  # noqa: BLE001  —— 旧版无 find_tables / 单页失败都跳过
                continue
            for t in (getattr(finder, "tables", None) or []):
                try:
                    rows = t.extract()
                except Exception:  # noqa: BLE001
                    continue
                md, nrows, ncols, conf = _table_rows_to_md(rows)
                if md is None:
                    continue
                table_no += 1
                tables_meta.append({"page": page_no, "rows": nrows, "cols": ncols, "confidence": conf})
                tag = "，低置信" if conf == "low" else ""
                md_parts.append(f"### 表 {table_no}（第 {page_no} 页，{nrows}×{ncols}{tag}）\n\n{md}")
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass

    if not tables_meta:
        return [], "", "none"

    status = "ok" if any(t["confidence"] == "ok" for t in tables_meta) else "low"
    header = (
        "\n\n---\n\n## 结构化抽取的表格（PyMuPDF，保数值列）\n\n"
        "> 以下表格由 PyMuPDF 按行×列重新抽取，用于补全 markitdown 可能丢失的数值列；"
        "括号内为来源页与行列数。与正文如有重复，以本节数值为准。\n\n"
    )
    return tables_meta, header + "\n\n".join(md_parts) + "\n", status


# ════════════════════════════════════════════════════════════════════
# 扫描版 PDF：OCR 回退
# ════════════════════════════════════════════════════════════════════
def ocr_pdf_if_possible(pdf_path):
    """
    若 ocrmypdf 可用，对扫描版 PDF 跑 OCR 生成临时 pdf 并返回其路径；
    不可用则返回 None（调用方据此标记 scanned 并给安装提示）。
    返回的临时文件由调用方负责清理。
    """
    if not shutil.which("ocrmypdf"):
        return None
    tmp_fd, tmp_pdf = tempfile.mkstemp(suffix=".ocr.pdf")
    os.close(tmp_fd)
    try:
        # --skip-text：已有文本层的页跳过，只 OCR 无文本页，避免重复
        subprocess.run(
            ["ocrmypdf", "--skip-text", "--quiet", pdf_path, tmp_pdf],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return tmp_pdf
    except subprocess.CalledProcessError as e:
        eprint(f"[normalize] 提示：ocrmypdf 执行失败（{e}），按扫描版处理且不再 OCR。")
        if os.path.exists(tmp_pdf):
            os.remove(tmp_pdf)
        return None


# ════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="阶段一：把单个文档归一化为 content.md + assets/ + meta.json"
    )
    parser.add_argument("input", help="输入文件路径")
    parser.add_argument("--out", required=True, help="工作区根目录（WORKSPACE_DIR）")
    parser.add_argument("--file-id", default=None,
                        help="该文件的稳定 id（如 f1）；缺省用安全文件名")
    args = parser.parse_args()

    in_path = os.path.abspath(args.input)
    if not os.path.isfile(in_path):
        eprint(f"[normalize] 错误：输入文件不存在：{in_path}")
        sys.exit(2)

    file_type = detect_file_type(in_path)
    name_dir = safe_name(in_path)
    file_id = args.file_id or name_dir

    out_root = os.path.abspath(args.out)
    doc_dir = os.path.join(out_root, name_dir)
    assets_dir = os.path.join(doc_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    content_path = os.path.join(doc_dir, "content.md")
    meta_path = os.path.join(doc_dir, "meta.json")

    eprint(f"[normalize] 处理：{in_path}  (type={file_type}, id={file_id})")

    # ── 1) markitdown 转换 ──
    md_text = convert_with_markitdown(in_path)

    scanned = False
    ocr_tmp = None
    is_pdf = (file_type == "pdf")

    # ── 2) 扫描版 PDF 判定 + OCR 回退 ──
    if is_pdf and visible_char_count(md_text) < SCANNED_TEXT_THRESHOLD:
        eprint("[normalize] 检测到 PDF 正文极少，疑为扫描版，尝试 OCR 回退…")
        ocr_tmp = ocr_pdf_if_possible(in_path)
        if ocr_tmp:
            eprint("[normalize] ocrmypdf 完成，重新转换 OCR 后的 PDF。")
            md_text = convert_with_markitdown(ocr_tmp)
            # OCR 后若仍极少，也标记 scanned 以示警
            scanned = visible_char_count(md_text) < SCANNED_TEXT_THRESHOLD
        else:
            scanned = True
            eprint("[normalize] 未找到 ocrmypdf（或 OCR 失败）。建议：brew install ocrmypdf。"
                   "本文件按扫描版处理，正文可能为空。")

    # ── 3) 写 content.md（分块写，确保超长不截断）──
    with open(content_path, "w", encoding="utf-8", newline="\n") as f:
        chunk = 1 << 20  # 1MB
        for i in range(0, len(md_text), chunk):
            f.write(md_text[i:i + chunk])

    # ── 4) 标题索引 ──
    headings = parse_headings(md_text)

    # ── 5) PDF 专属：抽图 + 标题页码定位（fitz 缺失则安全降级）──
    assets = []
    # 抽图/定位都基于「实际被转换的 pdf」：扫描版若 OCR 成功用 OCR 版，否则用原版
    pdf_for_fitz = ocr_tmp if (is_pdf and ocr_tmp) else (in_path if is_pdf else None)

    tables_meta = []
    table_status = None       # "ok" | "low" | "none" | None(非 PDF / fitz 不可用)
    if is_pdf:
        fitz = _try_import_fitz()
        if fitz is not None and pdf_for_fitz:
            assets = pdf_extract_assets(fitz, pdf_for_fitz, assets_dir)
            headings = pdf_locate_heading_pages(fitz, pdf_for_fitz, headings)
            # 表格结构化抽取 → 追加进 content.md，并登记到 meta
            tables_meta, appendix_md, table_status = pdf_extract_tables(fitz, pdf_for_fitz)
            if appendix_md:
                try:
                    with open(content_path, "a", encoding="utf-8", newline="\n") as f:
                        f.write(appendix_md)
                    eprint(f"[normalize] 表格结构化抽取：{len(tables_meta)} 张（status={table_status}），已追加进 content.md。")
                except OSError as e:
                    eprint(f"[normalize] 提示：追加表格到 content.md 失败（{e}）。")
        else:
            # fitz 不可用：标题页码全部置 None，照常产出
            headings = [dict(h, page=None) for h in headings]
    else:
        # 非 PDF：没有可靠页码概念，page 一律 None
        headings = [dict(h, page=None) for h in headings]

    # ── 6) 页数统计（PDF 用 fitz/已抽过的页文本；非 PDF 为 None）──
    pages = None
    if is_pdf and pdf_for_fitz:
        fitz2 = _try_import_fitz()
        if fitz2 is not None:
            try:
                d = fitz2.open(pdf_for_fitz)
                pages = d.page_count
                d.close()
            except Exception:  # noqa: BLE001
                pages = None

    # ── 7) 组装并写 meta.json ──
    meta = {
        "file_id": file_id,
        "file_name": os.path.basename(in_path),
        "file_type": file_type,
        "pages": pages,
        "words": count_words(md_text),
        "date": guess_date(md_text, in_path),
        "scanned": bool(scanned),
        "assets": assets,                # [{path, page}]
        "heading_index": headings,       # [{level, title, page|None}]
        "tables": tables_meta,           # [{page, rows, cols, confidence}]（PDF 结构化抽表登记）
        "table_extraction": table_status,  # ok|low|none|None —— low/none 提示阶段二回查原件
    }
    with open(meta_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ── 8) 清理 OCR 临时文件 ──
    if ocr_tmp and os.path.exists(ocr_tmp):
        try:
            os.remove(ocr_tmp)
        except OSError:
            pass

    # ── 完成提示 ──
    eprint(
        f"[normalize] 完成 → {doc_dir}\n"
        f"            content.md ({len(md_text)} chars, {meta['words']} words), "
        f"assets={len(assets)}, headings={len(headings)}, "
        f"pages={pages}, scanned={scanned}"
    )
    # stdout 输出产出目录，便于调用方捕获
    print(doc_dir)


if __name__ == "__main__":
    main()
