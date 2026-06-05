# 安装 doc-atlas skill

克隆到你的用户级技能目录即可：

```bash
git clone https://github.com/LeifDiao/doc-atlas.git ~/.claude/skills/doc-atlas
```

**解析依赖不打包进仓库，也不用你手动装。** 首次使用本技能时，它会检查 markitdown + PyMuPDF（约 290MB）是否就绪；没装会**先征求你同意再安装**（uv + python3.11 建一个隔离 `.venv`，1–2 分钟，之后复用）。**不同意就不会装**，但也就无法解析文档。

> 想提前手动装好也行（可选）：`bash ~/.claude/skills/doc-atlas/scripts/bootstrap.sh`

## 运行依赖

- 归一化：`uv` + `python3.11`（脚本会用它建 `.venv` 装 `markitdown[pdf,docx,pptx,xlsx,xls]` + `pymupdf`）。扫描版 PDF 的 OCR 回退需要可选的 `ocrmypdf`（`brew install ocrmypdf`）。
- 渲染 / 自检：系统 `/usr/bin/python3` + `playwright`（自检无头渲染；本机有 Chrome 时会自动回退到 `channel="chrome"`）。

## 怎么用

在你**装着 PDF/文档的文件夹**里触发本技能（自然语言「梳理/生成面板/可视化总结」，或 `/doc-atlas`）。它会：

0. **先问你要哪种语言的面板**（中文 / English / 跟随原文）；
1. **扫描**当前文件夹列出候选文档，**与你确认**要纳入哪些；
2. 把确认的文件**归一化**为 Markdown 中间层（`content.md` + `assets/` + `meta.json`）；
3. 跨文件**去重/识冲突/互补**，重组成 `model.json`；
4. **渲染**出单文件离线 `dashboard.html`（左目录树 + 右模块化内容），并无头**自检**。

产物默认落在该文件夹下的 `./doc-atlas-out/`。

## 先看效果

直接用浏览器打开 `examples/example-dashboard.html` 就是一份成品面板示例。
