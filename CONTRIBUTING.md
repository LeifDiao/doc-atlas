# Contributing

Contributions are welcome.

## The pipeline

doc-atlas is a Claude Code skill with a deterministic rendering core:

```
scan_docs.py → normalize.py → (AI writes model.json) → render_dashboard.py → selfcheck.py
```

The **hard boundary**: the AI produces a structured `model.json`; the renderer turns it into
HTML. The AI never hand-writes HTML, and the renderer never invents content. Keep that line
intact — it is what makes output stable, headless-checkable, and token-efficient.

## Where to make changes

- **Rendering / layout** → `scripts/render_dashboard.py` + `templates/dashboard.html`.
- **Data shape** → `schema/model.schema.json` (draft-07). When you change it, update the
  human docs in `references/model-schema.md` and `references/merge-and-structure.md` to
  match, and keep `examples/example-model.json` valid.
- **Normalization / scanning** → `scripts/normalize.py`, `scripts/scan_docs.py`.
- **Workflow / behavior** → `SKILL.md` (the skill entry point) and `references/`.

## Development checks

The scripts are plain Python 3. `render_dashboard.py` and `selfcheck.py` use only the
standard library plus Playwright (for the self-check); normalization uses markitdown +
PyMuPDF, installed on first use into an isolated `.venv`.

```bash
# Syntax-check the scripts
python3 -m py_compile scripts/scan_docs.py scripts/normalize.py \
  scripts/render_dashboard.py scripts/selfcheck.py

# Render the bundled example model into a dashboard (positional: model.json, out.html)
python3 scripts/render_dashboard.py examples/example-model.json /tmp/example.html

# Headless self-check (needs playwright + a Chromium/Chrome)
python3 scripts/selfcheck.py /tmp/example.html

# Or render and self-check in one step
python3 scripts/render_dashboard.py examples/example-model.json /tmp/example.html --self-check
```

Validate a `model.json` against the schema before rendering (any draft-07 validator works),
and confirm the example still renders without console errors after a change.

## Design principles

- **AI → `model.json`, renderer → HTML.** Never let the AI emit HTML; never hand-write the
  rendered output.
- **Deterministic rendering.** Given the same `model.json`, `render_dashboard.py` produces
  the same `dashboard.html`. Keep rendering free of randomness and network calls.
- **Escape untrusted source content.** Text, tables, captions, and diagram/chart specs come
  from the user's documents and are untrusted. The template escapes content via `esc()` and
  the data is embedded through `_serialize_and_escape()`; never interpolate source text into
  the DOM or the `<script>` payload without going through them.
- **Self-contained output.** Images are inlined as base64; only Chart.js / Mermaid load from
  a CDN. Don't add new runtime CDNs or trackers to the template.
- **Keep heavy deps optional and isolated.** markitdown / PyMuPDF / OCR install only with the
  user's consent, into a reused `.venv`. Don't add outbound network calls to the scripts.
- **Render only when there is data.** Right-side modules appear only if the corresponding
  `model.json` field is present — keep that "no data → no module" behavior.
