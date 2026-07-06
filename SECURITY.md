# Security

doc-atlas processes documents on your machine and renders a local, self-contained HTML
dashboard. Its helper scripts make **no outbound network calls**; parsing dependencies are
installed (with your consent) from PyPI on first use. By default the generated dashboard
inlines Chart.js and Mermaid and makes **zero network requests** when opened (an opt-in
`--cdn` render mode loads them from a public CDN instead).

## Reporting Issues

If you find a security issue, please open a private report through GitHub security
advisories when available, or contact the maintainer through the GitHub profile linked in
this repository. Please do not file public issues for security-sensitive reports.

## Security-sensitive areas

- **HTML injection from document content.** Text, tables, captions, quotes, and diagram /
  chart specifications all originate from the documents you feed in, which are
  attacker-influenceable. The renderer escapes content via `esc()` in
  `templates/dashboard.html` and embeds the data through `_serialize_and_escape()` in
  `render_dashboard.py` (the model is delivered inside a `<script type="application/json">`
  block and parsed with `JSON.parse`). A bug that lets source content reach the DOM or break
  out of that script payload unescaped is a security issue. `validate_model.py` additionally
  rejects structurally invalid models before they are rendered.
- **Third-party rendering libraries.** The dashboard renders charts with Chart.js and
  diagrams with Mermaid, **inlined from `templates/vendor/`** (pinned versions listed in
  that folder's README; the renderer defends the inline boundary by escaping any stray
  `</script>`). Mermaid is initialized with `securityLevel:'strict'`. Those libraries
  execute model-provided chart/diagram specs in the browser, so keep the vendored versions
  current and treat diagram/chart source as untrusted input to them.
- **Parsing untrusted files.** Normalization runs untrusted PDFs / Office files through
  markitdown, PyMuPDF, and (optionally) OCR. These parse complex binary formats — keep the
  dependencies updated, and treat a crafted document as potentially hostile input.
- **Dependency installation.** The first-use install is consent-gated and lands in an
  isolated `.venv`. Pin versions where practical and never install silently.
- **Local path handling.** `scan_docs.py`, `normalize.py`, and `render_dashboard.py` read
  from the working folder and write `workspace/` and the output dashboard — guard against
  path traversal via crafted filenames or output paths, and do not read outside the intended
  directories.

## What doc-atlas does to limit exposure

It keeps the scripts offline, gates heavy dependency installation behind explicit consent in
an isolated environment, validates the model before rendering, escapes untrusted document
content before it reaches the rendered HTML, and inlines images and the two pinned
charting/diagram libraries as local content rather than fetching anything — so the default
dashboard runs entirely offline with no external runtime requests.
