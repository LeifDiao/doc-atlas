# Doc Atlas

> **把一份或多份文档（PDF / Word / PPT / Excel / HTML / EPUB / Markdown…）梳理整合成一个精美的、离线可开的单文件可视化信息面板的 Claude Code 技能。**

🌏 [English](./README.md) · 🖥 [在线页面](https://leifdiao.github.io/doc-atlas/) · 🧩 [看样例面板](https://leifdiao.github.io/doc-atlas/sample-dashboard.html) · 📝 [更新日志](./CHANGELOG.md) · ⚖️ [许可](./LICENSE)

---

左侧是统一目录树，右侧是按内容自动选取的模块：执行摘要、首屏关键指标卡、**大尺寸逻辑/关系图（核心卖点，可点击放大）**、数据图表（Chart.js）、冲突对照、章节详情。一切结论都带来源角标，可溯源回「哪个文件第几页」。运行时先扫描、再**一次性与你确认输出语言和纳入哪些文件**。

三条核心追求：**① 高度炼化**（看面板就够、不必翻原文）、**② 准确可溯**（零幻觉、不确定就诚实标注、过一道对抗式核查）、**③ 逻辑图是主角**（把核心因果/关系做成醒目大图）。

## 它能做什么

- **多格式归一化** — 任意文档先转成 Markdown 中间层（`content.md` + `assets/` + `meta.json`）；**PDF 逐页插入页锚 `<!-- [doc-atlas] p.N -->`，每条结论的页码有机器依据**；**表格按行×列结构化抽取保住数值列**；扫描版 PDF 自动走 OCR 回退；源文件未变自动增量跳过。
- **跨文件梳理合并** — 多文件自动去重、识别冲突（数字/日期/结论不一致时显式列出而非静默选一个）、互补整合、判断文件关系，而不是逐文件摘要。
- **高度炼化 + 可信** — 三层阅读模型（概览/要点/细节）、首屏关键指标卡、**炼化体检表**（覆盖率/压缩比/待核实占比，由 `validate_model.py` 机器强制执行阈值）、**对抗式事实核查**（回原件证伪、验算派生数字）。
- **结构化渲染** — AI 只产出结构化 `model.json`，渲染前先过机器校验闸（结构/交叉引用/页码越界/炼化阈值），再由确定性渲染器编译成单文件 `dashboard.html`（图片 base64 内嵌，**Chart.js / Mermaid 整体内联，零外链、断网可开**）。
- **「纸本」皮肤** — 暖米纸 + 蓝色墨（重点/风险保留朱红）+ 无衬线正文的杂志式版面，关键数字自动高亮、宽松密度，逻辑图整行大图。
- **交互** — 「只看重点 / 展开全部」一键切换、关系图点击放大、全文搜索（高亮+跳转，自动展开命中章节）、目录树折叠 + 滚动高亮、重要度/来源筛选、中英界面随选定语言切换。

## 支持的格式

归一化用 [markitdown](https://github.com/microsoft/markitdown)，支持：

- **PDF**（含扫描版 → OCR 回退）、**Word `.docx`**、**PowerPoint `.pptx`**、**Excel `.xlsx`**
- **HTML**、**EPUB**、**Markdown `.md`**、**纯文本 `.txt`**、**CSV / JSON / XML**

> 旧版二进制格式（`.doc` / `.ppt` / `.xls`，2007 前）markitdown 可能无法直接解析，先用 Office/LibreOffice 另存为新格式（`.docx` 等）再处理。

## 工作流（六步）

0. **扫描 + 一次性确认** — 先扫描当前文件夹列出候选文档，再一次性与你确认**输出语言 + 纳入哪些文件**；
1. **归一化** — 每个文件 → `workspace/<name>/{content.md, assets/, meta.json}`（PDF 逐页页锚 + 表格结构化抽取保数值列）；
2. **梳理合并（核心）** — 跨文件去重 / 识冲突 / 互补，重组成 `model.json`，并填炼化体检 + 完整性批判第二遍；
3. **事实核查（对抗式）** — 对外/高风险文档派 subagent 回原件证伪、验算派生数字，修正后再渲染；
4. **渲染** — 过 `validate_model.py` 机器校验后，`model.json (+workspace)` → 单文件 `dashboard.html`（零外链）；
5. **自检交付** — playwright 无头校验无报错 + 抽查溯源，并把炼化体检/核查结论讲给你。

## 安装

```bash
git clone https://github.com/LeifDiao/doc-atlas.git ~/.claude/skills/doc-atlas
```

装好后，在**装着文档的文件夹**里用自然语言触发（「帮我梳理这些文档/生成面板」）或 `/doc-atlas`。**首次使用**会在征得你同意后自动安装解析依赖（markitdown + PyMuPDF，约 290MB，装进隔离 `.venv`，之后复用）；不同意则不安装、也无法解析。详见 [INSTALL.md](INSTALL.md)。

## 先看效果

浏览器直接打开 [`examples/example-dashboard.html`](examples/example-dashboard.html) 就是一份成品面板示例，或在线看 [样例面板](https://leifdiao.github.io/doc-atlas/sample-dashboard.html)。

## 目录结构

```
doc-atlas/
├── SKILL.md                  技能主入口（六步工作流）
├── INSTALL.md                安装说明
├── scripts/
│   ├── scan_docs.py          阶段零：扫描候选文档
│   ├── bootstrap.sh          建 .venv + 装依赖
│   ├── normalize.py          阶段一：文档 → content.md/assets/meta.json（PDF 页锚）
│   ├── validate_model.py     阶段二末尾：结构/交叉引用/页码/阈值机器校验
│   ├── render_dashboard.py   阶段三：model.json → 单文件 dashboard.html
│   ├── build_examples.sh     从 example-model.json 重新生成两份示例面板
│   └── selfcheck.py          阶段四：playwright 无头自检
├── templates/dashboard.html  固定前端模板（内联 CSS/JS）
├── templates/vendor/         内联用的 Chart.js / Mermaid 副本（MIT）
├── tests/                    pytest 单测 + 集成冒烟
├── schema/model.schema.json  model.json 的 JSON Schema（draft-07）
├── references/               阶段二梳理指南 + model.json 说明
└── examples/                 全特性示例 model.json + 成品面板
```

## 运行依赖

- **归一化**：首次经你同意装 `markitdown[pdf,docx,pptx,xlsx,xls]` + `pymupdf`（约 290MB，装进隔离 `.venv`，之后复用）。建 venv 优先用 `uv`，没有 uv 自动回退 `python3 -m venv`（需要 python ≥ 3.10）；扫描版 PDF 的 OCR 回退可选装 `ocrmypdf`。
- **渲染 / 校验**：任意系统 `python3`（纯标准库）。
- **自检（可选）**：`playwright`——`bash scripts/bootstrap.sh --with-selfcheck` 可装进 `.venv`，selfcheck 会自动使用；两处都没有时降级为静态检查。

## 设计

AI 写中间表示（`model.json`），渲染器出 HTML —— AI 从不手写 HTML，所以每次产出结构稳定、可无头自检、省 token。右侧模块「有数据才渲染」，每个章节由有序「区块」自由编排（段落 / 提示框 / 要点 / 引用 / 逻辑图 / 图表 / 表格 / 图片 / 子节点），兼顾稳定与灵活。

## 参与贡献

欢迎提 Issue 和 PR——见 [CONTRIBUTING.md](./CONTRIBUTING.md)。AI 产出 `model.json`、渲染器出 HTML 这条边界要守住；改渲染就改 `render_dashboard.py` + `templates/dashboard.html`，改结构就同步 `schema/model.schema.json` 和 `references/`。

## 许可

以 [CC BY-NC 4.0](./LICENSE) 发布：个人 / 教育 / 研究等非商业用途免费，商业用途需单独授权（leifdiao@gmail.com）。
