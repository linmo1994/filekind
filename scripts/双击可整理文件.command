#!/bin/bash
# 双击运行：将 ./待整理 中的文件按项目整理到 ./已整理
set -euo pipefail

# macOS Terminal 默认 bash 退出时会打印 "Saving session..." 等，与 filekind 无关
if [[ "${OSTYPE:-}" == darwin* ]]; then
  export SHELL_SESSIONS_DISABLE=1
  unset -f shell_session_save shell_session_save_user_state 2>/dev/null || true
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

pause_on_exit() {
  echo ""
  { read -r -p "按回车键关闭窗口…" _; } </dev/tty 2>/dev/null || \
    { read -r -p "按回车键关闭窗口…" _; } 2>/dev/null || true
}

# 双击时 Terminal 常在成功后立刻关窗；无论成败都暂停以便看到输出
trap pause_on_exit EXIT

macos_authorize() {
  xattr -dr com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true
  chmod +x "$0" 2>/dev/null || true
  if [[ -f "$SCRIPT_DIR/filekind" ]]; then
    chmod +x "$SCRIPT_DIR/filekind"
    codesign --force --sign - "$SCRIPT_DIR/filekind" 2>/dev/null || true
  fi
  codesign --force --sign - "$0" 2>/dev/null || true
}

ensure_config() {
  if [[ ! -f "$SCRIPT_DIR/projects.yaml" && -f "$SCRIPT_DIR/projects.example.yaml" ]]; then
    cp "$SCRIPT_DIR/projects.example.yaml" "$SCRIPT_DIR/projects.yaml"
    echo "已从 projects.example.yaml 生成 projects.yaml。"
  fi
}

ensure_dirs() {
  mkdir -p "$SCRIPT_DIR/待整理" "$SCRIPT_DIR/已整理" "$SCRIPT_DIR/项目清单"
}

repo_root() {
  local candidate="$SCRIPT_DIR/../.."
  if [[ -f "$candidate/pyproject.toml" ]]; then
    (cd "$candidate" && pwd)
  fi
}

venv_filekind_with_llm() {
  local root="$1"
  local py="$root/.venv/bin/python"
  local fk="$root/.venv/bin/filekind"
  [[ -x "$py" && -x "$fk" ]] || return 1
  "$py" -c "import llama_cpp" 2>/dev/null || return 1
  echo "$fk"
}

frozen_filekind() {
  [[ -f "$SCRIPT_DIR/filekind" && -d "$SCRIPT_DIR/_internal" ]] || return 1
  echo "$SCRIPT_DIR/filekind"
}

resolve_filekind() {
  local root vf ff
  root="$(repo_root || true)"
  if [[ -n "$root" ]]; then
    vf="$(venv_filekind_with_llm "$root" || true)"
    if [[ -n "$vf" ]]; then
      echo "$vf"
      return 0
    fi
  fi
  ff="$(frozen_filekind || true)"
  if [[ -n "$ff" ]]; then
    echo "$ff"
    return 0
  fi
  if command -v filekind >/dev/null 2>&1; then
    command -v filekind
    return 0
  fi
  return 1
}

check_bundle() {
  if resolve_filekind >/dev/null; then
    return 0
  fi
  echo "未找到 filekind 可执行文件。" >&2
  echo "请复制完整的 dist/filekind 目录，或运行 scripts/build_executable.sh 打包。" >&2
  if [[ ! -d "$SCRIPT_DIR/_internal" ]]; then
    echo "若使用打包版，需包含 _internal/ 目录。" >&2
  fi
  exit 1
}

inbox_has_files() {
  find "$SCRIPT_DIR/待整理" -type f \
    ! -name '.DS_Store' \
    ! -path '*/.*' \
    -print -quit 2>/dev/null | grep -q .
}

llm_gguf_setting() {
  grep -E '^[[:space:]]*llm_gguf:' "$SCRIPT_DIR/projects.yaml" 2>/dev/null | head -1 \
    | sed -E 's/.*:[[:space:]]*"?([^"#]+)"?.*/\1/' | tr -d '"' | xargs || true
}

resolve_llm_model_path() {
  local rel="$1"
  [[ -n "$rel" ]] || return 1
  if [[ "$rel" == /* ]]; then
    echo "$rel"
  else
    echo "$SCRIPT_DIR/$rel"
  fi
}

describe_engine() {
  local runner="$1"
  local llm_rel llm_path
  llm_rel="$(llm_gguf_setting || true)"
  if [[ -n "$llm_rel" ]]; then
    llm_path="$(resolve_llm_model_path "$llm_rel" || true)"
    if [[ -n "$llm_path" && -f "$llm_path" ]]; then
      echo "    LLM 模型: $llm_path"
    else
      echo "    LLM: 已配置但未找到模型文件 ($llm_rel)" >&2
      echo "    运行: python scripts/download_llm_model.py" >&2
    fi
  fi
  if [[ "$runner" == *"/.venv/"* ]]; then
    echo "    引擎: Python 开发环境（含 LLM）"
  else
    echo "    引擎: 打包版 filekind"
  fi
}

macos_authorize
ensure_config
ensure_dirs
check_bundle

FILEKIND="$(resolve_filekind)" || {
  echo "未找到 filekind。请先运行 scripts/build_executable.sh 打包。" >&2
  exit 1
}

if ! inbox_has_files; then
  echo "待整理/ 目录为空，没有可处理的文件。" >&2
  echo "请先将待整理文件放入: $SCRIPT_DIR/待整理" >&2
  exit 1
fi

INVENTORY_NAME="$(grep -E '^[[:space:]]*inventory_excel:' projects.yaml 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"?([^"#]+)"?.*/\1/' | tr -d '"' | xargs || true)"

if [[ -n "$INVENTORY_NAME" ]]; then
  if ! find "$SCRIPT_DIR/待整理" "$SCRIPT_DIR/项目清单" -name "$INVENTORY_NAME" -print -quit 2>/dev/null | grep -q .; then
    echo "提示: 配置中的清单文件尚未放入 待整理/ 或 项目清单/ : $INVENTORY_NAME" >&2
    echo "运行时将尝试自动识别清单，或请您选择一个 Excel 文件。" >&2
  fi
fi

echo "==> filekind 整理"
echo "    工作目录: $SCRIPT_DIR"
echo "    待整理 → 已整理"
echo "    项目清单: 自动识别或运行中选择"
echo "    使用说明: $SCRIPT_DIR/使用说明.txt"
describe_engine "$FILEKIND"
echo ""

"$FILEKIND" run --apply --no-dry-run --confirm --open-dest
