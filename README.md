# Doc Atlas

> **A Claude Code skill that distills one or more documents (PDF / Word / PPT / Excel /
> HTML / EPUB / Markdown…) into a single, polished, offline, self-contained visual
> dashboard.**

🌏 [中文版](./README_zh.md) · 🖥 [Live page](https://leifdiao.github.io/doc-atlas/) · 🧩 [Sample dashboard](https://leifdiao.github.io/doc-atlas/sample-dashboard.html) · 📝 [Changelog](./CHANGELOG.md) · ⚖️ [License](./LICENSE)

> **中文简介：** 把一份或多份文档梳理整合成一个精美、离线可开的单文件可视化信息面板的 Claude Code 技能。左侧统一目录树，右侧按内容自动选取模块（摘要 / 关键指标卡 / 大尺寸逻辑关系图 / 图表 / 冲突对照 / 章节详情），每条结论都能溯源回「哪个文件第几页」。完整中文文档 → [README_zh.md](./README_zh.md)

---

A left-hand unified table-of-contents tree; on the right, modules chosen automatically by
what the content needs: an executive summary, first-screen key-metric cards, a
**large logic / relationship diagram (the centerpiece — click to zoom)**, data charts
(Chart.js), conflict comparisons, and chapter details. Every claim carries a source badge
and traces back to *which file, which page*. On each run it scans first, then **confirms
the dashboard language and file selection with you in a single prompt**.

Three core pursuits: **① highly distilled** (the dashboard is enough — no need to open the
source), **② accurate and traceable** (zero hallucination, honest "unverified" flags, run
through an adversarial fact-check), and **③ the logic diagram is the star** (turn the core
causality / relationships into a prominent, large diagram).

## What it does

- **Multi-format normalization** — any document is first converted to a Markdown
  intermediate layer (`content.md` + `assets/` + `meta.json`); **PDFs get a per-page anchor
  `<!-- [doc-atlas] p.N -->` so every cited page number has a machine basis**; **tables are
  extracted row × column to keep numeric columns intact**; scanned PDFs fall back to OCR
  automatically; unchanged sources are skipped incrementally.
- **Cross-file consolidation** — multiple files are de-duplicated, conflicts are surfaced
  (when numbers / dates / conclusions disagree, they are listed explicitly rather than
  silently picking one), gaps are filled in, and file relationships are inferred — not a
  file-by-file summary.
- **Highly distilled + trustworthy** — a three-layer reading model (overview / key points /
  detail), first-screen metric cards, a **distillation report** (coverage / compression
  ratio / share still to verify — thresholds machine-enforced by `validate_model.py`), and
  an **adversarial fact-check** (refute against the source, recompute derived numbers).
- **Structured rendering** — the AI only produces a structured `model.json`, which passes
  a machine validation gate (structure / cross-references / page bounds / distillation
  thresholds) and is then compiled by a deterministic renderer into a single-file
  `dashboard.html` (images inlined as base64; **Chart.js / Mermaid inlined too — zero
  external requests, truly opens offline**).
- **A "paper" skin** — warm rice-paper + blue ink (vermilion kept for emphasis / risk) +
  a sans-serif body in a magazine-style layout; key numbers auto-highlighted, generous
  density, the logic diagram rendered full-width.
- **Interaction** — one-click "key points only / expand all", click-to-zoom diagrams,
  full-text search (highlight + jump, auto-expanding the matched chapter), a collapsible
  TOC tree with scroll highlighting, importance / source filters, and a Chinese / English
  UI that follows the language you chose.

## Supported formats

Normalization uses [markitdown](https://github.com/microsoft/markitdown), which supports:

- **PDF** (incl. scanned → OCR fallback), **Word `.docx`**, **PowerPoint `.pptx`**,
  **Excel `.xlsx`**
- **HTML**, **EPUB**, **Markdown `.md`**, **plain text `.txt`**, **CSV / JSON / XML**

> Legacy binary formats (`.doc` / `.ppt` / `.xls`, pre-2007) may not parse directly in
> markitdown — re-save them as a modern format (`.docx`, etc.) in Office / LibreOffice
> first.

## Workflow (six steps)

0. **Scan + one-shot confirmation** — scan the current folder, list candidate documents,
   then confirm **the dashboard language and which files to include in a single prompt**;
1. **Normalize** — each file → `workspace/<name>/{content.md, assets/, meta.json}` (PDFs
   get per-page anchors; tables extracted structurally to keep numeric columns);
2. **Consolidate (the core)** — de-duplicate / detect conflicts / complement across files,
   reassemble into `model.json`, and fill in the distillation report + a second
   completeness critique;
3. **Fact-check (adversarial)** — for outward-facing / high-risk documents, dispatch a
   subagent to refute against the source and recompute derived numbers, then re-render;
4. **Render** — after the `validate_model.py` gate, `model.json (+ workspace)` → single-file `dashboard.html` (zero external links);
5. **Self-check & deliver** — a headless Playwright check for errors + spot-checking
   sources, then walk you through the distillation report / fact-check findings.

## Install

```bash
git clone https://github.com/LeifDiao/doc-atlas.git ~/.claude/skills/doc-atlas
```

Once installed, trigger it in natural language from **the folder that holds your documents**
("help me make sense of these docs / build a dashboard") or with `/doc-atlas`. **On first
use** it installs the parsing dependencies after asking your consent (markitdown + PyMuPDF,
~290 MB, into an isolated `.venv`, reused afterward); decline and it installs nothing and
cannot parse. See [INSTALL.md](INSTALL.md).

## See it first

Open [`examples/example-dashboard.html`](examples/example-dashboard.html) directly in a
browser for a finished sample dashboard, or view the
[sample dashboard online](https://leifdiao.github.io/doc-atlas/sample-dashboard.html).

## Project structure

```
doc-atlas/
├── SKILL.md                  skill entry point (the workflow)
├── INSTALL.md                install notes
├── scripts/
│   ├── scan_docs.py          stage 0: scan candidate documents
│   ├── bootstrap.sh          create .venv + install dependencies
│   ├── normalize.py          stage 1: document → content.md/assets/meta.json (PDF page anchors)
│   ├── validate_model.py     stage-2 gate: structure / cross-refs / page bounds / thresholds
│   ├── render_dashboard.py   stage 3: model.json → single-file dashboard.html
│   ├── build_examples.sh     regenerate both sample dashboards from example-model.json
│   └── selfcheck.py          stage 4: headless Playwright self-check
├── templates/dashboard.html  fixed front-end template (inlined CSS/JS)
├── templates/vendor/         inlined copies of Chart.js / Mermaid (MIT)
├── tests/                    pytest unit + integration smoke tests
├── schema/model.schema.json  JSON Schema for model.json (draft-07)
├── references/               stage-2 consolidation guide + model.json spec
└── examples/                 full-feature sample model.json + finished dashboard
```

## Runtime dependencies

- **Normalization:** on first use, with your consent, it installs
  `markitdown[pdf,docx,pptx,xlsx,xls]` + `pymupdf` (~290 MB into an isolated `.venv`, reused
  afterward). The venv is created with `uv` when available, falling back to
  `python3 -m venv` (python ≥ 3.10); OCR fallback for scanned PDFs can optionally use
  `ocrmypdf`.
- **Rendering / validation:** any system `python3` (pure stdlib).
- **Self-check (optional):** `playwright` — install into the `.venv` via
  `bash scripts/bootstrap.sh --with-selfcheck`; selfcheck picks it up automatically and
  degrades to a static check when unavailable.

## Design

The AI writes an intermediate representation (`model.json`) and the renderer emits the HTML
— the AI never hand-writes HTML, so every run is structurally stable, headless-checkable,
and token-efficient. Right-side modules render **only when there is data**, and each chapter
is freely composed from ordered "blocks" (paragraph / callout / key points / quote / diagram
/ chart / table / image / subsections), balancing stability and flexibility.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](./CONTRIBUTING.md). Hold the line that the AI
produces `model.json` and the renderer produces HTML; change rendering in
`render_dashboard.py` + `templates/dashboard.html`, and keep `schema/model.schema.json` and
`references/` in sync when the structure changes.

## License

Released under [CC BY-NC 4.0](./LICENSE): free for personal / educational / research and
other non-commercial use; commercial use requires a separate license (leifdiao@gmail.com).
