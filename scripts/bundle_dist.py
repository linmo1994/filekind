#!/usr/bin/env python3
"""Stage config templates and inbox folders into dist/filekind after PyInstaller."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "filekind"


def main() -> int:
    if sys.platform == "win32":
        binary = DIST / "filekind.exe"
    else:
        binary = DIST / "filekind"

    if not binary.is_file():
        print(f"Build output not found: {binary}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    for name in (
        "projects.example.yaml",
        "classify_prompts.example.yaml",
    ):
        src = ROOT / name
        dst = DIST / name
        shutil.copy2(src, dst)
        shutil.copy2(src, DIST / name.replace(".example", ""))

    for folder in ("待整理", "已整理"):
        (DIST / folder).mkdir(parents=True, exist_ok=True)

    if sys.platform == "darwin":
        launcher = ROOT / "scripts" / "双击可整理文件.command"
        if launcher.is_file():
            target = DIST / launcher.name
            shutil.copy2(launcher, target)
            target.chmod(0o755)
    elif sys.platform == "win32":
        launcher = ROOT / "scripts" / "run-filekind.bat"
        if launcher.is_file():
            shutil.copy2(launcher, DIST / launcher.name)

    print(f"Bundle ready: {DIST}")
    print(f"Binary: {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
