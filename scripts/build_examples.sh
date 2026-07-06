#!/usr/bin/env bash
#
# build_examples.sh —— 从 examples/example-model.json 重新生成两份示例面板：
#   examples/example-dashboard.html   （仓库内直接打开的成品示例）
#   docs/sample-dashboard.html        （GitHub Pages 在线样例）
#
# 两份产物必须始终来自同一次渲染，防止手工同步漂移。
# 改了模板 / 渲染器 / example-model.json 之后跑一次本脚本再提交。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
PY="$(command -v python3)"

"$PY" "$SKILL_DIR/scripts/render_dashboard.py" \
  "$SKILL_DIR/examples/example-model.json" \
  "$SKILL_DIR/examples/example-dashboard.html" \
  --workspace "$SKILL_DIR/examples/"

cp "$SKILL_DIR/examples/example-dashboard.html" "$SKILL_DIR/docs/sample-dashboard.html"

echo "[build_examples] 已生成："
echo "  - examples/example-dashboard.html"
echo "  - docs/sample-dashboard.html（同一次渲染的拷贝）"
