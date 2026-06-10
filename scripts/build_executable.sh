#!/usr/bin/env bash
# Build standalone filekind executable (macOS / Linux).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel -q
pip install -e ".[dev]" -q
pip install pyinstaller -q

pyinstaller --noconfirm --clean filekind.spec

OUT="$ROOT/dist/filekind/filekind"
if [[ ! -x "$OUT" ]]; then
  echo "Build failed: $OUT not found" >&2
  exit 1
fi

# Convenience bundle: config template next to binary
cp -f projects.example.yaml dist/filekind/projects.yaml
cp -f projects.example.yaml dist/filekind/projects.example.yaml
cp -f classify_prompts.example.yaml dist/filekind/classify_prompts.yaml
cp -f classify_prompts.example.yaml dist/filekind/classify_prompts.example.yaml
cp -f scripts/双击可整理文件.command dist/filekind/双击可整理文件.command
mkdir -p dist/filekind/待整理 dist/filekind/已整理
chmod +x dist/filekind/双击可整理文件.command

if [[ "$(uname -s)" == "Darwin" ]]; then
  xattr -cr dist/filekind 2>/dev/null || true
  codesign --force --sign - "$OUT" 2>/dev/null || true
  codesign --force --sign - dist/filekind/双击可整理文件.command 2>/dev/null || true
fi

echo ""
echo "Build complete."
echo "  Binary:  $OUT"
echo "  Folder:  $ROOT/dist/filekind/"
echo "  Double-click: dist/filekind/双击可整理文件.command"
echo ""
echo "Quick start:"
echo "  cd dist/filekind"
echo "  # 将文件放入 ./待整理，然后双击 双击可整理文件.command"
echo "  # 或在终端: ./filekind run --apply --no-dry-run"
echo ""
echo "Note: first run may download embedding model (~100MB) to ~/.cache."
echo "Optional LLM/OCR are not bundled; use source install for those features."
