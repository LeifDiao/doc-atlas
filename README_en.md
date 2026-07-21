# Doc Atlas

> **A Claude Code skill that distills one or more documents (PDF / Word / PPT / Excel /
> HTML / EPUB / Markdown…) into a single, polished, offline, self-contained visual
> dashboard.**

🌏 [中文版](./README.md) · 🖥 [Live page](https://lemomo-ai.github.io/doc-atlas/) · 🧩 [Sample dashboard](https://lemomo-ai.github.io/doc-atlas/sample-dashboard.html) · 📝 [Changelog](./CHANGELOG.md) · ⚖️ [License](./LICENSE)

> **中文简介：** 把一份或多份文档梳理整合成一个精美、离线可开的单文件可视化信息面板的 Claude Code 技能。左侧统一目录树，右侧是一条固定阅读主线（一句话定论 / 关键指标卡 / 大尺寸逻辑关系图 / 图表 / 冲突对照 / 折叠章节详情），每条结论都能溯源回「哪个文件第几页」。完整中文文档 → [README.md](./README.md)

<img width="2082" height="1177" alt="Screenshot 2026-07-10 at 10 26 55 AM" src="https://github.com/user-attachments/assets/1fd4d2b6-3a50-40c7-8073-1e4cd1b3976d" />

> 🆕 **v1.0.0** — renewed end-to-end with **Claude Fable 5**: a redesigned "paper briefing"
> UI with a one-sentence verdict up top, goal-driven distillation (it now asks *what you
> want out of the documents* and grades importance against that), and trust metrics that
> are audited against ground truth instead of self-reported. Details in the
> [changelog](./CHANGELOG.md).

---

A left-hand unified table-of-contents tree; on the right, a fixed briefing spine: **a
one-sentence verdict (The Bottom Line)**, first-screen key-metric cards, an executive
summary, a **large logic / relationship diagram (the centerpiece — click to zoom)**, data
charts (Chart.js), tiered key points, conflict comparisons, collapsed chapter details, and
a quiet appendix (source files / relations / distillation check). Every claim carries a
source badge and traces back to *which file, which page*. On each run it scans first, then
**confirms the dashboard language, file selection, and your reading goal in a single
prompt** — the whole distillation is graded against the question you actually brought.

Three core pursuits: **① highly distilled** (the dashboard is enough — no need to open the
source), **② accurate and traceable** (zero hallucination, honest "unverified" flags, run
through an adversarial fact-check whose per-claim findings render in the appendix), and
**③ the logic diagram is the star** (turn the core causality / relationships into a
prominent, large diagram).

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
- **Highly distilled + trustworthy** — a three-layer reading model (verdict & overview /
  key points / detail), first-screen metric cards, a **distillation report** (coverage /
  compression ratio / share still to verify — thresholds machine-enforced and **reconciled
  against the workspace ground truth** by `validate_model.py`), and an **adversarial
  fact-check** (refute against the source, recompute derived numbers) whose per-claim
  verdicts render as an expandable table in the appendix.
- **Structured rendering** — the AI only produces a structured `model.json`, which passes
  a machine validation gate (structure / cross-references / page bounds / distillation
  thresholds) and is then compiled by a deterministic renderer into a single-file
  `dashboard.html` (images inlined as base64; **Chart.js / Mermaid inlined too — zero
  external requests, truly opens offline**).
- **A "paper briefing" skin** — warm rice-paper + blue ink (vermilion kept for emphasis /
  risk) with a fixed reading spine: verdict → numbered briefing sections → collapsed
  chapters → a visually quiet appendix. One page has exactly one class of big numbers
  (the key metrics); document stats shrink to a masthead line ("source ≈ 62 min → this
  page ≈ 7 min"); prose uses the full content width.
- **Interaction** — one-click "briefing only / expand all", click-to-zoom diagrams,
  full-text search (highlight + jump, auto-expanding the matched chapter), a collapsible
  TOC tree with scroll highlighting, importance / source filters tucked into a sidebar
  tool drawer, and a Chinese / English UI that follows the language you chose.

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
   then confirm **the dashboard language, which files to include, and your reading goal in
   a single prompt** (the goal drives importance grading, metric selection, and the
   verdict);
1. **Normalize** — each file → `workspace/<name>/{content.md, assets/, meta.json}` (PDFs
   get per-page anchors; tables extracted structurally to keep numeric columns);
2. **Consolidate (the core)** — de-duplicate / detect conflicts / complement across files,
   keep an auditable concepts inventory (`_concepts.jsonl`), reassemble into `model.json`,
   and fill in the distillation report + a second completeness critique;
3. **Fact-check (adversarial)** — for outward-facing / high-risk documents, dispatch a
   subagent to refute against the source and recompute derived numbers; findings land in
   `factcheck.json` and render as a per-claim table in the dashboard appendix;
4. **Render** — after the `validate_model.py` gate, `model.json (+ workspace)` → single-file `dashboard.html` (zero external links);
5. **Self-check & deliver** — a headless Playwright check for errors + spot-checking
   sources, then walk you through the distillation report / fact-check findings.

## Install

```bash
git clone https://github.com/lemomo-ai/doc-atlas.git ~/.claude/skills/doc-atlas
```

Once installed, trigger it in natural language from **the folder that holds your documents**
("help me make sense of these docs / build a dashboard") or with `/doc-atlas`. **On first
use** it installs the parsing dependencies after asking your consent (markitdown + PyMuPDF,
~290 MB, into an isolated `.venv`, reused afterward); decline and it installs nothing and
cannot parse. See [INSTALL.md](INSTALL.md).

## See it first

Open [`examples/example-dashboard.html`](examples/example-dashboard.html) directly in a
browser for a finished sample dashboard, or view the
[sample dashboard online](https://lemomo-ai.github.io/doc-atlas/sample-dashboard.html).

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
