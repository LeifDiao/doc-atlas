# Contributing

Contributions are welcome.

## The pipeline

doc-atlas is a Claude Code skill with a deterministic rendering core:

```
scan_docs.py → normalize.py → (AI writes model.json) → validate_model.py → render_dashboard.py → selfcheck.py
```

The **hard boundary**: the AI produces a structured `model.json`; the renderer turns it into
HTML. The AI never hand-writes HTML, and the renderer never invents content. Keep that line
intact — it is what makes output stable, headless-checkable, and token-efficient.

## Where to make changes

- **Rendering / layout** → `scripts/render_dashboard.py` + `templates/dashboard.html`.
- **Data shape** → `schema/model.schema.json` (draft-07). When you change it, update the
  matching validator in `scripts/validate_model.py`, the human docs in
  `references/model-schema.md` and `references/merge-and-structure.md`, and keep
  `examples/example-model.json` valid.
- **Normalization / scanning** → `scripts/normalize.py`, `scripts/scan_docs.py`.
- **Bundled libraries** → `templates/vendor/` (Chart.js / Mermaid, inlined into every
  dashboard). See `templates/vendor/README.md` for how to upgrade.
- **Workflow / behavior** → `SKILL.md` (the skill entry point) and `references/`.

## Development checks

`validate_model.py`, `render_dashboard.py`, and `selfcheck.py` are plain Python 3 with only
the standard library (selfcheck additionally uses Playwright when available); normalization
uses markitdown + PyMuPDF, installed on first use into an isolated `.venv`.

```bash
# Unit + integration tests
pip install pytest && pytest tests/ -q

# Validate a model.json (structure / cross-refs / page bounds / distillation thresholds)
python3 scripts/validate_model.py examples/example-model.json

# Render the bundled example (validation runs automatically before rendering)
python3 scripts/render_dashboard.py examples/example-model.json /tmp/example.html \
  --workspace examples/

# Headless self-check (uses Playwright; auto-switches to the .venv python if needed)
python3 scripts/selfcheck.py /tmp/example.html

# Regenerate both sample dashboards from one render (prevents drift)
bash scripts/build_examples.sh
```

`render_dashboard.py` runs `validate_model.py` automatically and refuses to render an invalid
model. After any change to the schema, renderer, or template, run `pytest`, regenerate the
examples, and confirm the dashboard still renders without console errors.

## Design principles

- **AI → `model.json`, renderer → HTML.** Never let the AI emit HTML; never hand-write the
  rendered output.
- **Deterministic rendering.** Given the same `model.json`, `render_dashboard.py` produces
  the same `dashboard.html`. Keep rendering free of randomness and network calls.
- **Escape untrusted source content.** Text, tables, captions, and diagram/chart specs come
  from the user's documents and are untrusted. The template escapes content via `esc()` and
  the data is embedded through `_serialize_and_escape()`; never interpolate source text into
  the DOM or the `<script>` payload without going through them.
- **Self-contained output.** Images are inlined as base64, and Chart.js / Mermaid are
  inlined from `templates/vendor/` — the default dashboard makes **zero network requests**.
  Don't add new runtime CDNs or trackers to the template; keep the `--cdn` path as an
  explicit opt-out only.
- **Keep heavy deps optional and isolated.** markitdown / PyMuPDF / OCR install only with the
  user's consent, into a reused `.venv`. Don't add outbound network calls to the scripts.
- **Render only when there is data.** Right-side modules appear only if the corresponding
  `model.json` field is present — keep that "no data → no module" behavior.
