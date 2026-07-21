# 安装 doc-atlas skill

克隆到你的用户级技能目录即可：

```bash
git clone https://github.com/lemomo-ai/doc-atlas.git ~/.claude/skills/doc-atlas
```

**解析依赖不打包进仓库，也不用你手动装。** 首次使用本技能时，它会检查 markitdown + PyMuPDF（约 290MB）是否就绪；没装会**先征求你同意再安装**（建一个隔离 `.venv`：有 `uv` 用 uv，没有则回退 `python3 -m venv`，需要 python ≥ 3.10，1–2 分钟，之后复用）。**不同意就不会装**，但也就无法解析文档。

> 想提前手动装好也行（可选）：`bash ~/.claude/skills/doc-atlas/scripts/bootstrap.sh`

## 运行依赖

- 归一化：`.venv` 里的 `markitdown[pdf,docx,pptx,xlsx,xls]` + `pymupdf`（bootstrap 自动装；建 venv 优先 `uv`，无 uv 回退 `python3 -m venv`，python ≥ 3.10）。扫描版 PDF 的 OCR 回退需要可选的 `ocrmypdf`（macOS：`brew install ocrmypdf`）。
- 渲染 / 校验：任意系统 `python3`（纯标准库，含渲染前的 `validate_model.py` 机器校验）。
- 自检（可选）：`playwright`——`bash scripts/bootstrap.sh --with-selfcheck` 装进 `.venv` 后 selfcheck 自动使用；本机有 Chrome 时会自动回退 `channel="chrome"`；两者都没有则降级静态检查。

## 怎么用

在你**装着 PDF/文档的文件夹**里触发本技能（自然语言「梳理/生成面板/可视化总结」，或 `/doc-atlas`）。它会：

0. **扫描**当前文件夹列出候选文档，**一次性与你确认**输出语言（中文 / English / 跟随原文）和纳入哪些文件；
1. （首次）征求你同意后安装解析依赖；
2. 把确认的文件**归一化**为 Markdown 中间层（`content.md` + `assets/` + `meta.json`）；
3. 跨文件**去重/识冲突/互补**，重组成 `model.json`；
4. **渲染**出单文件 `dashboard.html`（左目录树 + 右模块化内容，Chart.js/Mermaid 已内联、零外链、断网可开），渲染前过机器校验、渲染后无头**自检**。

产物默认落在该文件夹下的 `./doc-atlas-out/`。

## 先看效果

直接用浏览器打开 `examples/example-dashboard.html` 就是一份成品面板示例。
