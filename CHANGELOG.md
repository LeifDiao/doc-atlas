# Changelog

All notable changes to doc-atlas are documented here.
This project adheres to [Semantic Versioning](https://semver.org/) and the
[Keep a Changelog](https://keepachangelog.com/) format.

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

[0.2.0]: https://github.com/LeifDiao/doc-atlas/releases/tag/v0.2.0
[0.1.0]: https://github.com/LeifDiao/doc-atlas/releases/tag/v0.1.0
