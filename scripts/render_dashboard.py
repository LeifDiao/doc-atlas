#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_dashboard.py — 阶段三渲染器：model.json (+workspace) → 单文件 dashboard.html

把阶段二产出的 model.json（唯一中间表示 IR）编译成一个**单文件**、**离线可打开**的
可视化信息面板。所有本地图片在此被读出并以 data:URI 形式内嵌，因此输出 HTML 可能较大，
这是预期取舍（离线可用 > 体积小）。

纯标准库实现（json / base64 / mimetypes / argparse / pathlib / html / re / sys / os / datetime /
subprocess / shutil）。任意系统 python3 即可运行。

用法：
    python3 render_dashboard.py MODEL_JSON OUT_HTML [--workspace DIR] [--template PATH] [--self-check]

参数：
    MODEL_JSON        阶段二产出的 model.json 路径（utf-8）。
    OUT_HTML          输出的 dashboard.html 路径。
    --workspace DIR   workspace 根目录，用于定位 block.image.src 等相对图片路径。
                      缺省 = MODEL_JSON 所在目录。
    --template PATH   前端模板路径。缺省 = 本脚本同级 ../templates/dashboard.html。
    --self-check      渲染成功后调用同级 selfcheck.py 校验 OUT_HTML（selfcheck 缺 playwright
                      时会自动切到 .venv），并把其退出码并入本进程退出码。
    --cdn             不内联 Chart.js/Mermaid，改用 CDN 外链（输出依赖网络；缺省内联、断网可开）。
    --skip-validate   跳过渲染前的 validate_model.py 校验（不建议）。

退出码语义：
    0   渲染成功（且 --self-check 时自检也通过）。
    2   致命的输入问题：model.json 读不出 / 不是合法 JSON / 缺关键字段(meta/files/outline/
        chapters) / files 为空 / 模板找不到或模板里 __DASHBOARD_DATA__ 注入位出现次数 != 1。
    3   渲染过程中其它 I/O 错误（写文件失败等）。
    （--self-check 时，若渲染成功但自检失败，则以 selfcheck.py 的非零退出码退出。）

注入契约（必须与 templates/dashboard.html 严格一致）：
    模板里恰好包含一行注入位：
        <script id="dashboard-data" type="application/json">__DASHBOARD_DATA__</script>
    本脚本把已完成"图片→dataURI 内嵌"的整个 model 用 json.dumps(ensure_ascii=False) 序列化，
    再把 < > & 三个字符转义成 \\u003c \\u003e \\u0026（防止 JSON 字符串里出现 </script> 提前
    闭合脚本、或 & 触发 HTML 实体解析），最后用 str.replace 把唯一的 __DASHBOARD_DATA__ 替换掉。
"""

import argparse
import base64
import datetime
import html  # noqa: F401  （保留在标准库导入清单中，供潜在扩展使用）
import json
import mimetypes
import os
import re  # noqa: F401  （保留在标准库导入清单中，供潜在扩展使用）
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------------------------ 常量 -----

# 模板里唯一的数据注入 token
DATA_TOKEN = "__DASHBOARD_DATA__"

# 模板里唯一的前端库注入 token（整行 HTML 注释，渲染时被替换为内联脚本或 CDN 标签）
VENDOR_TOKEN = "<!-- __VENDOR_JS__ -->"

# vendor 库清单：templates/vendor/ 下的文件名 + 版本（升级时同步 vendor/README.md）
VENDOR_LIBS = [
    ("chart.umd.min.js", "chart.js@4.4.1"),
    ("mermaid.min.js", "mermaid@10.9.1"),
]

# --cdn 时使用的外链（旧行为；输出将依赖网络才能渲染图与图表）
VENDOR_CDN_TAGS = (
    '<!-- doc-atlas:vendor cdn -->\n'
    '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>'
)

# 顶层必须存在的字段（致命缺字段拦截，完整校验交给 schema/）
REQUIRED_TOP_KEYS = ("meta", "files", "outline", "chapters")

# 常见图片扩展名 → 当 mimetypes 猜不出时用于兜底判断是否"看起来像图片路径"
IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
    ".svg", ".tif", ".tiff", ".ico", ".avif",
}

# mimetypes 猜不出时的默认 MIME（按契约默认 image/png）
DEFAULT_IMAGE_MIME = "image/png"

# 通用兜底扫描只在这些字段名下做图片内嵌（防止把 md/text 里"恰好以 .png 结尾"的
# 普通文本误替换成 dataURI）
GENERIC_IMAGE_KEYS = {"src", "image", "img", "icon", "logo", "cover", "images"}


# ----------------------------------------------------------------- 工具函数 --

def _eprint(*args):
    """统一往 stderr 打印（warning / error）。"""
    print(*args, file=sys.stderr)


def _looks_like_local_image(value):
    """
    判断一个字符串是否"看起来像本地图片路径"。
    规则：是 str、非空、不是已内嵌的 data: URI、不是 http(s) 远程地址，
    且扩展名落在 IMAGE_EXTS 内（大小写不敏感）。
    """
    if not isinstance(value, str) or not value:
        return False
    low = value.strip().lower()
    if low.startswith("data:"):       # 已经是 dataURI，不再处理
        return False
    if low.startswith(("http://", "https://", "//")):  # 远程图片，不内嵌
        return False
    ext = os.path.splitext(low)[1]
    return ext in IMAGE_EXTS


def _resolve_image_path(src, workspace):
    """
    图片定位策略：先按绝对路径找，找不到再按 (workspace / src) 找。
    返回存在的 Path，或 None（找不到）。

    - 若 src 本身是绝对路径且存在 → 直接用。
    - 否则尝试 workspace / src。
    - 再退一步：若 src 是绝对路径但不存在，也尝试用其文件名拼到 workspace（容错，通常不命中）。
    """
    p = Path(src)
    # 1) 绝对路径直接命中
    if p.is_absolute() and p.is_file():
        return p
    # 2) workspace / src（相对路径的主路径）
    if workspace is not None:
        cand = (Path(workspace) / src)
        if cand.is_file():
            return cand
    # 3) 非绝对路径也可能相对于当前工作目录存在
    if not p.is_absolute() and p.is_file():
        return p.resolve()
    return None


def _image_to_data_uri(path):
    """
    读图片二进制 → base64 → data:URI。用 mimetypes 猜 MIME，猜不出用默认 image/png。
    读失败抛异常由调用方处理。
    """
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        mime = DEFAULT_IMAGE_MIME
    raw = Path(path).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return "data:%s;base64,%s" % (mime, b64)


class _ImageEmbedder:
    """
    遍历 model，把本地图片 src 原地替换为 dataURI。
    统计：embedded（成功内嵌数）、missing（找不到/读失败数）。
    去重缓存：同一路径只读一次。
    """

    def __init__(self, workspace):
        self.workspace = workspace
        self.embedded = 0
        self.missing = 0
        self._cache = {}  # 原始 src 字符串 -> dataURI（成功）或 ""（失败）

    def _embed_one(self, src):
        """把单个 src 转成 dataURI；失败返回空串并计 missing。带缓存。"""
        if src in self._cache:
            return self._cache[src]
        path = _resolve_image_path(src, self.workspace)
        if path is None:
            self.missing += 1
            _eprint("[warn] 图片未找到，已置空：%s" % src)
            self._cache[src] = ""
            return ""
        try:
            uri = _image_to_data_uri(path)
        except Exception as exc:  # 读失败/编码失败也算 missing，不崩
            self.missing += 1
            _eprint("[warn] 图片读取失败，已置空：%s (%s)" % (src, exc))
            self._cache[src] = ""
            return ""
        self.embedded += 1
        self._cache[src] = uri
        return uri

    # -- 针对 image block 的精准处理 ------------------------------------------
    def _process_image_block(self, block):
        """type=='image' 的 block：其 'src' 字段就是图片路径，原地替换。"""
        src = block.get("src")
        if isinstance(src, str) and src and not src.strip().lower().startswith("data:"):
            block["src"] = self._embed_one(src)

    # -- 通用兜底：递归扫描任意 dict/list，仅在图片字段名白名单下替换 --
    def _process_generic(self, node, key=None):
        """
        递归处理任意结构。仅当字段名落在 GENERIC_IMAGE_KEYS（src/image/…）里、
        且字符串"看起来像本地图片路径"时才替换为 dataURI——普通文本字段
        （md/text/caption…）即使恰好以 .png 结尾也不动，避免误伤正文。
        list 沿用父字段名判断（如 images: ["a.png", "b.png"]）。
        image block 已在 walk() 里被专门处理过，这里兜底其它可能的图片字段。
        """
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if isinstance(v, str):
                    if k in GENERIC_IMAGE_KEYS and _looks_like_local_image(v):
                        node[k] = self._embed_one(v)
                elif isinstance(v, (dict, list)):
                    self._process_generic(v, k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str):
                    if key in GENERIC_IMAGE_KEYS and _looks_like_local_image(v):
                        node[i] = self._embed_one(v)
                elif isinstance(v, (dict, list)):
                    self._process_generic(v, key)

    def walk(self, model):
        """
        主入口：先精准处理 chapters[].blocks 里的 image block（最常见、最权威的图片来源），
        再对整个 model 做一次通用兜底扫描（捕获任何其它明显的本地图片路径）。
        """
        # 1) 精准：章节区块里的 image block
        chapters = model.get("chapters")
        if isinstance(chapters, list):
            for ch in chapters:
                if not isinstance(ch, dict):
                    continue
                blocks = ch.get("blocks")
                if not isinstance(blocks, list):
                    continue
                for blk in blocks:
                    if isinstance(blk, dict) and blk.get("type") == "image":
                        self._process_image_block(blk)
        # 2) 兜底：整棵 model 通用扫描（image block 的 src 已被替换成 dataURI，
        #    _looks_like_local_image 会因 data: 前缀而跳过，不会重复处理）
        self._process_generic(model)


# ------------------------------------------------------------- 校验 / 主流程 --

def _load_model(model_path):
    """读 model.json 并做轻量致命校验。失败时打印并以退出码 2 退出。"""
    p = Path(model_path)
    if not p.is_file():
        _eprint("[error] MODEL_JSON 不存在：%s" % model_path)
        sys.exit(2)
    try:
        text = p.read_text(encoding="utf-8")
    except Exception as exc:
        _eprint("[error] 读取 MODEL_JSON 失败：%s" % exc)
        sys.exit(2)
    try:
        model = json.loads(text)
    except json.JSONDecodeError as exc:
        _eprint("[error] MODEL_JSON 不是合法 JSON：%s" % exc)
        sys.exit(2)
    if not isinstance(model, dict):
        _eprint("[error] MODEL_JSON 顶层必须是对象 {}。")
        sys.exit(2)

    # 轻量校验：只挡致命缺字段，不做严格 schema 校验（避免过脆）
    missing = [k for k in REQUIRED_TOP_KEYS if k not in model]
    if missing:
        _eprint("[error] model.json 缺少必需顶层字段：%s" % ", ".join(missing))
        sys.exit(2)
    files = model.get("files")
    if not isinstance(files, list) or len(files) == 0:
        _eprint("[error] model.json 的 files 必须为非空数组。")
        sys.exit(2)
    return model


def _fill_generated_at(model):
    """若 meta.generated_at 为空（None/缺失/空串），用当天日期补上。"""
    meta = model.get("meta")
    if not isinstance(meta, dict):
        return  # meta 异常时不强行处理；上层 _load_model 已保证 meta 存在
    val = meta.get("generated_at")
    if val in (None, "", False):
        meta["generated_at"] = datetime.date.today().isoformat()


def _load_template(template_path):
    """读模板并校验两个注入位各恰好出现一次。失败以退出码 2 退出。"""
    p = Path(template_path)
    if not p.is_file():
        _eprint("[error] 模板不存在：%s" % template_path)
        sys.exit(2)
    try:
        tpl = p.read_text(encoding="utf-8")
    except Exception as exc:
        _eprint("[error] 读取模板失败：%s" % exc)
        sys.exit(2)
    for token in (DATA_TOKEN, VENDOR_TOKEN):
        n = tpl.count(token)
        if n != 1:
            _eprint("[error] 模板中注入位 %s 必须恰好出现 1 次，实际出现 %d 次：%s"
                    % (token, n, template_path))
            sys.exit(2)
    return tpl


def _build_vendor_html(template_path, use_cdn):
    """
    组装前端库注入内容：
      - 默认：读取 templates/vendor/ 下的 Chart.js 与 Mermaid，整体内联为 <script>，
        输出零外链、断网可开（体积换离线，是本项目的既定取舍）。
      - --cdn 或 vendor 文件缺失：退回 CDN <script src> 标签（缺失时打警告）。
    内联时把 `</script` 防御性转义为 `<\\/script`（两库实测不含该串，纯保险；
    该转义仅可能落在 JS 字符串/正则里，语义等价）。
    """
    if use_cdn:
        return VENDOR_CDN_TAGS
    vendor_dir = Path(template_path).resolve().parent / "vendor"
    parts = []
    names = []
    for fname, label in VENDOR_LIBS:
        fp = vendor_dir / fname
        if not fp.is_file():
            _eprint("[warn] vendor 库缺失：%s —— 本次退回 CDN 外链（输出将依赖网络）。" % fp)
            return VENDOR_CDN_TAGS
        try:
            js = fp.read_text(encoding="utf-8")
        except Exception as exc:
            _eprint("[warn] vendor 库读取失败（%s）—— 本次退回 CDN 外链。" % exc)
            return VENDOR_CDN_TAGS
        js = js.replace("</script", "<\\/script").replace("</SCRIPT", "<\\/SCRIPT")
        parts.append("<script>/* doc-atlas:vendor %s (inline) */\n%s\n</script>" % (label, js))
        names.append(label)
    marker = "<!-- doc-atlas:vendor inline %s -->" % " ".join(names)
    return marker + "\n" + "\n".join(parts)


def _serialize_and_escape(model):
    """
    把 model 序列化为 JSON 字符串（不转义非 ASCII，保留中文），
    再把 < > & 转成 \\u003c \\u003e \\u0026，防止 </script> 提前闭合或 & 被 HTML 解析。
    注意：& 必须最先替换不重要，因为我们替换的是字面字符而非引用 \\u 序列里的反斜杠；
    这三次 replace 互不干扰（替换目标 < > & 不会出现在彼此的替换结果中）。
    """
    payload = json.dumps(model, ensure_ascii=False)
    payload = (
        payload
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return payload


def _module_counts(model):
    """统计各模块计数，用于摘要打印。"""
    def _len(key):
        v = model.get(key)
        return len(v) if isinstance(v, list) else 0
    return {
        "keypoints": _len("keypoints"),
        "diagrams": _len("diagrams"),
        "charts": _len("charts"),
        "conflicts": _len("conflicts"),
        "chapters": _len("chapters"),
    }


def _run_validate(model_path, workspace):
    """
    渲染前调用同级 validate_model.py（stdlib）做结构/交叉引用/页码越界/阈值校验。
    返回其退出码；脚本缺失则警告并返回 0（不阻断）。
    """
    validator = Path(__file__).resolve().parent / "validate_model.py"
    if not validator.is_file():
        _eprint("[warn] 未找到同级 validate_model.py，跳过渲染前校验：%s" % validator)
        return 0
    cmd = [sys.executable, str(validator), str(model_path)]
    if workspace:
        cmd += ["--workspace", str(workspace)]
    _eprint("[info] 渲染前校验：%s" % " ".join(cmd))
    try:
        proc = subprocess.run(cmd)
    except Exception as exc:
        _eprint("[warn] 调用 validate_model.py 失败：%s" % exc)
        return 1
    return proc.returncode


def _run_selfcheck(out_html):
    """
    渲染成功后调用同级 selfcheck.py（该脚本会在缺 playwright 时自动切换到 .venv python）。
    返回 selfcheck 进程的退出码；找不到 selfcheck.py 则警告并返回 0（不阻断主流程成功）。
    """
    selfcheck = Path(__file__).resolve().parent / "selfcheck.py"
    if not selfcheck.is_file():
        _eprint("[warn] 未找到同级 selfcheck.py，跳过自检：%s" % selfcheck)
        return 0
    import shutil as _shutil
    py = _shutil.which("python3") or sys.executable
    _eprint("[info] 运行自检：%s %s %s" % (py, selfcheck, out_html))
    try:
        proc = subprocess.run([py, str(selfcheck), str(out_html)])
    except Exception as exc:
        _eprint("[warn] 调用 selfcheck.py 失败：%s" % exc)
        return 1
    return proc.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="render_dashboard.py",
        description="model.json (+workspace) → 单文件 dashboard.html（纯 stdlib）",
    )
    parser.add_argument("model_json", help="阶段二产出的 model.json 路径")
    parser.add_argument("out_html", help="输出 dashboard.html 路径")
    parser.add_argument("--workspace", default=None,
                        help="workspace 根目录（定位相对图片）；缺省=MODEL_JSON 所在目录")
    parser.add_argument("--template", default=None,
                        help="模板路径；缺省=脚本同级 ../templates/dashboard.html")
    parser.add_argument("--self-check", action="store_true",
                        help="渲染后调用 selfcheck.py，并把其退出码并入本进程")
    parser.add_argument("--cdn", action="store_true",
                        help="不内联 Chart.js/Mermaid，改用 CDN 外链（输出依赖网络，缺省为内联）")
    parser.add_argument("--skip-validate", action="store_true",
                        help="跳过渲染前的 validate_model.py 结构/交叉引用校验（不建议）")
    args = parser.parse_args(argv)

    # --- 路径默认值解析 ---
    model_path = Path(args.model_json)
    out_path = Path(args.out_html)

    workspace = args.workspace
    if workspace is None:
        # 默认 = MODEL_JSON 所在目录
        workspace = str(model_path.resolve().parent)

    if args.template is not None:
        template_path = Path(args.template)
    else:
        # 默认 = 本脚本同级 ../templates/dashboard.html
        template_path = Path(__file__).resolve().parent.parent / "templates" / "dashboard.html"

    # --- 0) 渲染前校验：结构 / 交叉引用 / 页码越界 / 炼化阈值 ---
    if not args.skip_validate:
        rc = _run_validate(model_path, workspace)
        if rc != 0:
            _eprint("[error] model.json 未通过校验（validate_model.py 退出码 %d）。"
                    "请修正后重试；确须跳过可加 --skip-validate（不建议）。" % rc)
            return 2

    # --- 1) 读 + 轻校验 model.json ---
    model = _load_model(model_path)

    # --- 3) 补 generated_at（放在内嵌前，确保被序列化） ---
    _fill_generated_at(model)

    # --- 2) 图片 → dataURI 内嵌 ---
    embedder = _ImageEmbedder(workspace)
    embedder.walk(model)

    # --- 4) 读模板 + 校验注入位唯一 ---
    tpl = _load_template(template_path)

    # 序列化 + 转义 + token 替换（数据位 + 前端库注入位各一处）
    payload = _serialize_and_escape(model)
    vendor_html = _build_vendor_html(template_path, args.cdn)
    out_html = tpl.replace(DATA_TOKEN, payload).replace(VENDOR_TOKEN, vendor_html)

    # --- 5) 写 OUT_HTML ---
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_html, encoding="utf-8")
    except Exception as exc:
        _eprint("[error] 写出 OUT_HTML 失败：%s" % exc)
        return 3

    # 摘要打印（stdout）
    counts = _module_counts(model)
    size_kb = out_path.stat().st_size / 1024.0
    print("[ok] 已生成面板：%s (%.1f KB)" % (out_path, size_kb))
    print("     前端库：%s" % ("CDN 外链（依赖网络）" if "doc-atlas:vendor cdn" in vendor_html
                              else "已内联（零外链，断网可开）"))
    print("     内嵌图片：%d 张；缺失图片：%d 张" % (embedder.embedded, embedder.missing))
    print("     模块计数 → keypoints=%d diagrams=%d charts=%d conflicts=%d chapters=%d"
          % (counts["keypoints"], counts["diagrams"], counts["charts"],
             counts["conflicts"], counts["chapters"]))

    # --- 6) --self-check ---
    if args.self_check:
        rc = _run_selfcheck(out_path)
        if rc != 0:
            _eprint("[error] 自检未通过（selfcheck 退出码 %d）。" % rc)
            return rc
        print("[ok] 自检通过。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
