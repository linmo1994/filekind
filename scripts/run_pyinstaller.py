#!/usr/bin/env python3
"""Run PyInstaller with UTF-8-safe stdio (avoids Windows cp1252 UnicodeEncodeError)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _configure_stdio() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main() -> int:
    _configure_stdio()
    root = Path(__file__).resolve().parent.parent
    spec = root / "filekind.spec"
    if not spec.is_file():
        print(f"Spec not found: {spec}", file=sys.stderr)
        return 1
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec),
    ]
    return subprocess.call(cmd, cwd=str(root))


if __name__ == "__main__":
    raise SystemExit(main())
