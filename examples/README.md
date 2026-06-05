# 示例

- `example-model.json` — 一份覆盖全部特性的 `model.json`（多文件 / 冲突 / 关系图 / 图表 / 金句 / 三层大纲 / 全部 block 类型）。
- `assets/p1-img1.png` — 示例 `image` block 引用的图片。
- `example-dashboard.html` — 由上面两者渲染出的成品面板，可直接用浏览器打开预览效果。

重新生成：
```bash
SKILL_DIR="$HOME/.claude/skills/doc-atlas"
/usr/bin/python3 "$SKILL_DIR/scripts/render_dashboard.py" \
  "$SKILL_DIR/examples/example-model.json" \
  "$SKILL_DIR/examples/example-dashboard.html" \
  --workspace "$SKILL_DIR/examples"
```
