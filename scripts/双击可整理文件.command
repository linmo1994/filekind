#!/bin/bash
# 双击运行：将 ./待整理 中的文件按项目整理到 ./已整理
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

pause_on_exit() {
  echo ""
  read -r -p "按回车键关闭窗口…" _
}

trap 'if [[ $? -ne 0 ]]; then pause_on_exit; fi' EXIT

macos_authorize() {
  xattr -dr com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null || true
  if [[ -f "$SCRIPT_DIR/filekind" ]]; then
    chmod +x "$SCRIPT_DIR/filekind"
    codesign --force --sign - "$SCRIPT_DIR/filekind" 2>/dev/null || true
  fi
  chmod +x "$0" 2>/dev/null || true
}

resolve_filekind() {
  if [[ -x "$SCRIPT_DIR/filekind" ]]; then
    echo "$SCRIPT_DIR/filekind"
    return 0
  fi
  if command -v filekind >/dev/null 2>&1; then
    command -v filekind
    return 0
  fi
  return 1
}

INVENTORY_NAME="$(grep -E '^[[:space:]]*inventory_excel:' projects.yaml 2>/dev/null | head -1 | sed -E 's/.*:[[:space:]]*"?([^"#]+)"?.*/\1/' | tr -d '"' | xargs || true)"

macos_authorize

FILEKIND="$(resolve_filekind)" || {
  echo "未找到 filekind 可执行文件。请先运行 scripts/build_executable.sh 打包。" >&2
  exit 1
}

if [[ -n "$INVENTORY_NAME" ]]; then
  if ! find "$SCRIPT_DIR/待整理" -name "$INVENTORY_NAME" -print -quit 2>/dev/null | grep -q .; then
    echo "警告: 在 待整理/ 下未找到项目清单 Excel: $INVENTORY_NAME" >&2
    echo "请将清单放入 待整理/（可放在子目录），或在 projects.yaml 中配置 inventory_excel。" >&2
  fi
fi

"$FILEKIND" run --apply --no-dry-run
