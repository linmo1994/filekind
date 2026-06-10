#!/usr/bin/env python3
"""Smoke-test a PyInstaller build by running --help without console encoding issues."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    platform = (sys.argv[1] if len(sys.argv) > 1 else sys.platform).lower()
    if platform in ("windows", "win32"):
        exe = Path("dist/filekind/filekind.exe")
    else:
        exe = Path("dist/filekind/filekind")

    if not exe.is_file():
        print(f"Missing binary: {exe}", file=sys.stderr)
        return 1

    result = subprocess.run(
        [exe.name, "--help"],
        cwd=exe.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = (result.stdout or result.stderr or "").strip()
    if output:
        print(output[:400])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
