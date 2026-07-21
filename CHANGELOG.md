# Changelog

All notable changes to doc-atlas are documented here.
This project adheres to [Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/) format.

## [1.0.0] — 2026-07-10

A goal-driven briefing release, renewed end-to-end with **Claude Fable 5**. The previous
dashboard rendered a dozen equal-weight sections and left the reader to find the point;
this release gives every run a question to answer (the reading goal), redesigns the
dashboard around a single briefing spine with a one-sentence verdict on top, and stops
letting the distillation report grade its own homework.

### Added
- **Reading goal (stage 0).** The one-shot confirmation now also asks *what you want out
  of these documents* (decision / learning / risk review / data lookup / custom). The
  answer is stored as `meta.reading_goal` and drives importance grading, `highlights`
  selection, and the verdict — the whole pipeline now has a question to answer instead of
  summarizing generically.
- **`meta.one_liner` — "The Bottom Line".** A one-sentence verdict rendered as a large
  serif bar right under the masthead; it should directly answer the reading goal. Falls
  back to `executive_summary[0]` when absent. Plus optional `meta.schema_version`.
- **Fact-check detail contract.** Stage 2.5 findings now land in a structured
  `$OUT/factcheck.json` (`claim` / `verdict: ok|deviation|error|missing` / `source` /
  `note`) and flow back into `distillation_report.fact_check_items[]`; the dashboard
  appendix renders them as an expandable per-claim table — the evidence behind "why you
  can trust this briefing", not just a one-line summary.
- **Concepts inventory artifact.** Stage 2's concept→source table is now a first-class
  intermediate product (`workspace/_concepts.jsonl` with kept/merged/dropped dispositions),
  so `claims_total`-style metrics are counted rather than asserted, fact-checkers can audit
  what was dropped, and long-document batch reading can resume mid-way.
- **Ground-truth reconciliation in `validate_model.py`.** With `--workspace`, self-reported
  numbers are audited against `meta.json`: page counts must match exactly (error), word
  counts get a 20% tolerance (warning), and `sections_total` below the file count is
  flagged — the distillation report can no longer grade its own homework.
- 8 new tests (45 total) covering the new fields, fact-check-item validation, and the
  reconciliation checks.

### Changed
- **Dashboard rebuilt as a "paper briefing"** (same warm-paper temperament, new
  information structure): a fixed reading spine — verdict → numbered briefing sections
  (key metrics / executive summary / core logic / charts / key points / conflicts /
  quotes) → collapsed chapter cards → a visually quiet appendix (source files, file
  relations, distillation check). One page now has exactly **one** class of big numbers:
  document stats (pages / words / minutes) are demoted to a single masthead line — with a
  "source ≈ 62 min → this page ≈ 7 min" payoff note — leaving `highlights` as the only
  large figures.
- **Key points are tiered**: high-importance items get a featured list with a vermilion
  edge; the rest collapse into a compact two-column list. Conflicts render positions
  side-by-side with the resolution row beneath. Source badges shrink to one unified
  minimal style; number highlighting is restricted to the verdict, summary, and featured
  key points instead of the whole page.
- **Chart palette replaced** with five colors validated for lightness band, chroma floor,
  color-vision-deficiency separation, and contrast on the paper surface (the old dark teal
  and green read as gray and failed validation).
- Search and importance/source filters moved into a collapsible sidebar tool section; the
  sidebar now leads with the numbered briefing nav and the chapter tree.
- `SKILL.md` and `references/` updated throughout (stage-0 third question, one-liner
  guidance, concepts-inventory and fact-check contracts, reconciliation discipline).

### Fixed
- **Body text wrapped long before the available width** — the old template clamped prose
  to a 74-ch measure column; the verdict, summary, paragraphs, and tables now use the full
  content width (the summary flows into balanced columns on wide screens instead).

## [0.2.0] — 2026-07-06

A trust-and-polish release. The previous version *claimed* traceable sourcing and offline
output but neither was machine-backed; this release makes both real, adds a validation gate,
and reworks the dashboard's centerpiece (the logic diagram) and interactions.

### Added
- **Per-page source anchors for PDFs.** `normalize.py` now extracts PDF text page-by-page
  with PyMuPDF and inserts a `<!-- [doc-atlas] p.N -->` anchor before each page, plus a
  `page_map` in `meta.json` — so every `SourceRef.page` has a machine basis instead of a
  guess. (Previously markitdown produced flat PDF text with no page markers, leaving the
  headline "trace every claim to file + page" promise unsupported.)
- **`scripts/validate_model.py`** — a stdlib model-validation gate run automatically before
  rendering: structure / enums / unknown-field checks, cross-reference resolution
  (`quote_id` / `diagram_id` / `chart_id`, one-to-one outline↔chapter ids, `file_id` hits
  `files[]`), `SourceRef.page` bounds against each file's page count, and machine-enforced
  distillation thresholds. `render_dashboard.py` refuses to render an invalid model
  (`--skip-validate` to override).
- **Bundled Chart.js / Mermaid** in `templates/vendor/`, inlined into every dashboard —
  the default output makes **zero network requests** and opens fully offline. A visible
  fallback (data table for charts, source block for diagrams) shows if a library is ever
  missing.
- **Diagram zoom overlay** with fit-to-view, `+ / − / Fit / 100%` controls, wheel zoom, and
  drag-to-pan (was a fixed 60vw blow-up that clipped small diagrams).
- **Precise TOC navigation** — sub-nodes get `node-<id>` anchors so clicking `1.2.1` jumps to
  the exact subsection (with a flash highlight and auto-expand) instead of the chapter top.
- **`tests/`** — 37 pytest unit + integration tests, and **GitHub Actions CI** on Ubuntu +
  macOS.
- **`scripts/build_examples.sh`** — regenerates `examples/example-dashboard.html` and
  `docs/sample-dashboard.html` from a single render to prevent drift.
- Structured numeric fields in `distillation_report` (`sections_total/mapped`,
  `claims_total/with_source_count`, `todo_count/data_points`, `compression_ratio_x`) so the
  distillation thresholds are machine-checkable, not free text.
- Incremental normalization: unchanged sources (by mtime + size) are skipped (`--force` to
  re-run); `--file-id` alignment between normalize and `model.files[].id`.
- `date_source` in `meta.json` (`content` vs `mtime`) so mtime-derived dates are never used
  as authority in conflict resolution.

### Changed
- **Mermaid diagrams now follow the "paper" skin** (panel background, ink text, blue accent,
  skin font via `themeVariables`) — the centerpiece no longer floats in the default lavender
  theme.
- **Stage 0 asks once, not twice** — scan first, then confirm output language *and* file
  selection in a single `AskUserQuestion` prompt.
- **Scanned-PDF detection is per-page** (share of pages with a text layer) instead of a
  whole-document character threshold that misclassified short text PDFs.
- **`bootstrap.sh` is portable** — no hard-coded Homebrew path; uses `uv` when present and
  falls back to `python3 -m venv` (Python ≥ 3.10); `--with-selfcheck` installs Playwright +
  Chromium into the `.venv`.
- **`selfcheck.py` auto-switches to the `.venv` python** when the current interpreter lacks
  Playwright, and its static-mode check understands the inline-vendor output.
- Landing-page hero preview is now a clickable link to the real sample dashboard.
- READMEs (en/zh), `INSTALL.md`, `SECURITY.md`, `PRIVACY.md`, `CONTRIBUTING.md`,
  `SKILL.md`, and `references/` updated to match the above.

### Fixed
- Responsive breakpoint mismatch (CSS 920px vs JS 860px) that left the mobile sidebar stuck
  open between 861–920px; the floating menu button overlapping the masthead; and the mobile
  sidebar having no dismiss-on-tap backdrop.
- Print/"save as PDF" losing collapsed-chapter content — collapsed chapters are now forced
  open when printing.
- Generic image-embedding in the renderer no longer rewrites plain text fields that merely
  end in `.png`; it only touches whitelisted image fields (`src` / `image` / `icon` / …).

### Removed
- ~120 lines of dead appearance-panel / theme-tweak code (skin is fixed by design).

## [0.1.0]

Initial public release: multi-format normalization (markitdown + PyMuPDF, OCR fallback for
scanned PDFs), cross-file consolidation with conflict surfacing, an AI-authored `model.json`
IR compiled by a deterministic renderer into a single-file `dashboard.html` with the "paper"
skin, adversarial fact-check, and a distillation report.

[1.0.0]: https://github.com/lemomo-ai/doc-atlas/releases/tag/v1.0.0
[0.2.0]: https://github.com/lemomo-ai/doc-atlas/releases/tag/v0.2.0
[0.1.0]: https://github.com/lemomo-ai/doc-atlas/releases/tag/v0.1.0
