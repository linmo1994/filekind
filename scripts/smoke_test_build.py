#!/usr/bin/env python3
"""Smoke-test a PyInstaller build by running --help without console encoding issues."""

from __future__ import annotations

import os
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

    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    result = subprocess.run(
        [str(exe.resolve()), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    output = (result.stdout or result.stderr or "").strip()
    if output:
        print(output[:800])
    if result.returncode != 0:
        print(f"Smoke test failed with exit code {result.returncode}", file=sys.stderr)
        if result.stdout:
            print(f"stdout:\n{result.stdout[:2000]}", file=sys.stderr)
        if result.stderr:
            print(f"stderr:\n{result.stderr[:2000]}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
