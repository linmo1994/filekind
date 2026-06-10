#!/usr/bin/env python3
"""PyInstaller entry point for filekind."""

import multiprocessing
import sys
import warnings

warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+",
    category=Warning,
)

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

multiprocessing.freeze_support()

from filekind.cli import app

if __name__ == "__main__":
    app()
