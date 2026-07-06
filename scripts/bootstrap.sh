#!/usr/bin/env bash
#
# bootstrap.sh —— 幂等地建立隔离的 Python 虚拟环境，并安装归一化阶段
# （normalize.py）所需依赖：markitdown[pdf,docx,pptx,xlsx,xls] + pymupdf(fitz)。
#
# 用法：
#   bash scripts/bootstrap.sh [--with-selfcheck]
#     --with-selfcheck   顺带把 playwright 装进 .venv 并下载 chromium
#                        （selfcheck.py 缺 playwright 时会自动切到这个 venv）
#
# 可移植性：
#   - venv 创建优先用 uv（PATH 里任意位置），没有 uv 则回退 `python3 -m venv`；
#   - python 解释器按 3.12 → 3.11 → 3.10 → python3(≥3.10) 顺序探测；
#     markitdown 不支持 3.9 及更早版本，全都太旧时报错退出。
#   - 不依赖 Homebrew 安装路径，macOS（Intel/ARM）与 Linux 均可用。
#
# 重复运行不会报错；脚本结束时把 venv 的 python 绝对路径打印到 stdout 最后一行，
# 调用方可用它来执行 normalize.py：
#   "$(bash scripts/bootstrap.sh | tail -1)" scripts/normalize.py INPUT --out WORKSPACE

set -euo pipefail

# ── 参数 ──
WITH_SELFCHECK=0
for arg in "$@"; do
  case "$arg" in
    --with-selfcheck) WITH_SELFCHECK=1 ;;
    *) echo "[bootstrap] 未知参数：$arg（支持 --with-selfcheck）" >&2; exit 2 ;;
  esac
done

# ── 定位 SKILL 根目录（scripts/ 的上一级），不依赖调用方 cwd ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
VENV_DIR="$SKILL_DIR/.venv"
VENV_PY="$VENV_DIR/bin/python"

# ── 探测 uv（可选）与合适的 python（≥3.10，markitdown 的下限） ──
UV_BIN="$(command -v uv || true)"

find_python() {
  local cand
  for cand in python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        command -v "$cand"
        return 0
      fi
    fi
  done
  return 1
}

# ── 1) 若 .venv 不存在则创建（幂等：已存在就跳过） ──
if [ ! -x "$VENV_PY" ]; then
  if [ -n "$UV_BIN" ]; then
    echo "[bootstrap] 用 uv 创建虚拟环境：$VENV_DIR" >&2
    # uv 自带 python 管理：本机没有合适版本时会自动下载
    "$UV_BIN" venv --python 3.11 "$VENV_DIR" >&2
  else
    SYS_PY="$(find_python || true)"
    if [ -z "$SYS_PY" ]; then
      echo "[bootstrap] 错误：既没有 uv，也找不到 python ≥ 3.10。" >&2
      echo "            请先安装其一：https://docs.astral.sh/uv/ 或 python.org。" >&2
      exit 1
    fi
    echo "[bootstrap] 未找到 uv，回退 $SYS_PY -m venv 创建：$VENV_DIR" >&2
    "$SYS_PY" -m venv "$VENV_DIR" >&2
    "$VENV_PY" -m pip install --quiet --upgrade pip >&2
  fi
else
  echo "[bootstrap] 复用已存在的虚拟环境：$VENV_DIR" >&2
fi

# ── 2) 安装/更新依赖（重复运行只会确认已满足） ──
# 只装本 skill 真正用到的解析组件：pdf / docx / pptx / xlsx / xls。
# 故意不装 markitdown[all]（它还含 azure 文档智能、语音转写、youtube 等用不到的大件）。
echo "[bootstrap] 安装依赖：markitdown[pdf,docx,pptx,xlsx,xls] + pymupdf ..." >&2
if [ -n "$UV_BIN" ]; then
  "$UV_BIN" pip install --python "$VENV_PY" 'markitdown[pdf,docx,pptx,xlsx,xls]' pymupdf >&2
else
  "$VENV_PY" -m pip install --quiet 'markitdown[pdf,docx,pptx,xlsx,xls]' pymupdf >&2
fi

# ── 3) 可选：selfcheck 依赖（playwright + chromium） ──
if [ "$WITH_SELFCHECK" = "1" ]; then
  echo "[bootstrap] 安装 selfcheck 依赖：playwright + chromium（首次约 130MB）..." >&2
  if [ -n "$UV_BIN" ]; then
    "$UV_BIN" pip install --python "$VENV_PY" playwright >&2
  else
    "$VENV_PY" -m pip install --quiet playwright >&2
  fi
  "$VENV_PY" -m playwright install chromium >&2
fi

# ── 4) 把 venv python 的绝对路径作为最后一行打印到 stdout（供调用方捕获） ──
echo "[bootstrap] 完成。venv python =" "$VENV_PY" >&2
echo "$VENV_PY"
