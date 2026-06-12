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
pip install -e ".[dev,llm,ocr]" -q
pip install pyinstaller -q

pyinstaller --noconfirm --clean filekind.spec

python scripts/bundle_dist.py

OUT="$ROOT/dist/filekind/filekind"
if [[ ! -x "$OUT" ]]; then
  echo "Build failed: $OUT not found" >&2
  exit 1
fi

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
echo "LLM: bundled when built with .[llm]; place GGUF under dist/filekind/_系统/models/ (see scripts/download_llm_model.py)."
echo "OCR: bundled when built with .[ocr]; first OCR may download Chinese models to ~/.paddleocr/."
