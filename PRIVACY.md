# Privacy

doc-atlas runs on your machine. It processes the documents you point it at and writes the
dashboard locally. Its helper scripts make no outbound network calls of their own.

## Data Read

- The **document files** in the folder you run it in — their full content (text, tables,
  and embedded images), read to normalize and consolidate them.
- Your **language choice** for the dashboard, and which candidate files you confirm to
  include.

## Processing & the AI model

doc-atlas runs **inside Claude Code**. To consolidate, distill, and fact-check your
documents, their content is read and reasoned over by the AI model — which means document
content is processed by Claude as part of normal Claude Code operation, subject to
Anthropic's applicable terms. **Be mindful when pointing doc-atlas at confidential or
regulated documents**, the same as with any content you bring into an AI assistant.

## Network & External Services

- **The helper scripts make no network calls.** Scanning, normalization, rendering, and the
  self-check all run locally.
- **First use installs parsing dependencies** (markitdown + PyMuPDF, ~290 MB; optionally
  `ocrmypdf`) from PyPI, only after you consent, into an isolated `.venv` that is reused
  afterward. Decline and nothing is installed.
- **The generated `dashboard.html` loads two libraries from a public CDN** (Chart.js and
  Mermaid, via jsDelivr) when you open it with a network connection. Images are inlined as
  base64, so the rest of the file is self-contained. Remove those two `<script>` tags (or
  vendor the libraries locally) if you need a fully offline file.
- doc-atlas uploads **no telemetry or analytics** of its own.

## Data Written

- `workspace/<name>/{content.md, assets/, meta.json}` — the normalized intermediate layer
  for each file, written into your working folder.
- The final **`dashboard.html`** — a single self-contained file that embeds the distilled
  content and base64 images from your documents.
- `doc-atlas-out/` — local output, gitignored.

All of the above stay on your machine.

## Sharing

The dashboard is self-contained and **embeds your documents' distilled content and images**.
If you send the `dashboard.html` to someone, it carries that content with it — share it only
when you intend to.
