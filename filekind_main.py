#!/usr/bin/env python3
"""PyInstaller entry point for filekind."""

from __future__ import annotations

import multiprocessing
import sys
import warnings

from filekind.frozen_entry import (
    maybe_pause_after_auto_clerk,
    prepare_windows_frozen_default_argv,
    run_app,
)

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

if __name__ == "__main__":
    auto_clerk = prepare_windows_frozen_default_argv()
    exit_code = run_app()
    maybe_pause_after_auto_clerk(auto_clerk=auto_clerk)
    raise SystemExit(exit_code)
