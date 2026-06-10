#!/usr/bin/env python3
"""PyInstaller entry point for filekind."""

import warnings

warnings.filterwarnings(
    "ignore",
    message="urllib3 v2 only supports OpenSSL 1.1.1+",
    category=Warning,
)

from filekind.cli import app

if __name__ == "__main__":
    app()
