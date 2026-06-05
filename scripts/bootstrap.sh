#!/usr/bin/env bash
#
# bootstrap.sh —— 幂等地用 uv 建立隔离的 Python 3.11 虚拟环境，
# 并安装归一化阶段（normalize.py）所需依赖：markitdown[pdf,docx,pptx,xlsx,xls] + pymupdf(fitz)。
#
# 用法：
#   bash scripts/bootstrap.sh
# 重复运行不会报错；脚本结束时把 venv 的 python 绝对路径打印到 stdout，
# 调用方可用它来执行 normalize.py：
#   "$(bash scripts/bootstrap.sh | tail -1)" scripts/normalize.py INPUT --out WORKSPACE
#
# 依赖前提（本机已探明）：
#   - uv 在 /opt/homebrew/bin/uv
#   - python3.11 在 /opt/homebrew/bin/python3.11
#   markitdown 无法装在系统 3.9，故这里强制用 3.11。

set -euo pipefail

# ── 定位 SKILL 根目录（scripts/ 的上一级），不依赖调用方 cwd ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"

UV_BIN="/opt/homebrew/bin/uv"
PY311="3.11"

# ── 健壮性：uv 必须存在 ──
if [ ! -x "$UV_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
  else
    echo "[bootstrap] 错误：未找到 uv（期望在 /opt/homebrew/bin/uv）。请先 'brew install uv'。" >&2
    exit 1
  fi
fi

# ── 1) 若 .venv 不存在则创建（幂等：已存在就跳过） ──
if [ ! -x "$VENV_PY" ]; then
  echo "[bootstrap] 创建虚拟环境（python ${PY311}）：${VENV_DIR}" >&2
  "$UV_BIN" venv --python "$PY311" "$VENV_DIR" >&2
else
  echo "[bootstrap] 复用已存在的虚拟环境：$VENV_DIR" >&2
fi

# ── 2) 安装/更新依赖（uv pip install 本身幂等，重复运行只会确认已满足） ──
# 只装本 skill 真正用到的解析组件：pdf / docx / pptx / xlsx / xls。
# 故意不装 markitdown[all]（它还含 azure 文档智能、语音转写、youtube 等用不到的大件）。
echo "[bootstrap] 安装依赖：markitdown[pdf,docx,pptx,xlsx,xls] + pymupdf ..." >&2
"$UV_BIN" pip install --python "$VENV_PY" 'markitdown[pdf,docx,pptx,xlsx,xls]' pymupdf >&2

# ── 3) 把 venv python 的绝对路径作为最后一行打印到 stdout（供调用方捕获） ──
echo "[bootstrap] 完成。venv python =" "$VENV_PY" >&2
echo "$VENV_PY"
