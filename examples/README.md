# 示例

- `example-model.json` — 一份覆盖全部特性的 `model.json`（多文件 / 冲突 / 关系图 / 图表 / 金句 / 三层大纲 / 全部 block 类型 / 数值化 `distillation_report`）。
- `assets/p1-img1.png` — 示例 `image` block 引用的图片。
- `example-dashboard.html` — 由上面两者渲染出的成品面板，**Chart.js/Mermaid 已内联、零外链，可直接用浏览器离线打开**。

重新生成（同时更新 `examples/` 与 `docs/` 两份，防漂移）：
```bash
bash scripts/build_examples.sh
```

或单独渲染一份：
```bash
python3 scripts/render_dashboard.py examples/example-model.json \
  examples/example-dashboard.html --workspace examples/
```

