# Vendored front-end libraries

These files are inlined into every rendered `dashboard.html` by
`scripts/render_dashboard.py` so the output is **fully self-contained and opens
offline with zero network requests** (pass `--cdn` to the renderer to use CDN
`<script src>` tags instead).

| File | Package | Version | License |
|---|---|---|---|
| `chart.umd.min.js` | [chart.js](https://www.chartjs.org/) | 4.4.1 | MIT |
| `mermaid.min.js` | [mermaid](https://mermaid.js.org/) | 10.9.1 | MIT |

To upgrade, download the minified UMD builds from jsDelivr/npm, replace the
files, update this table and the version strings in `render_dashboard.py`
(`VENDOR_LIBS`), then re-run the test suite and `scripts/build_examples.sh`.
