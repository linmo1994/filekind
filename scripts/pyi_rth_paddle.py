"""PyInstaller runtime hook: paddle.base.core calls set_paddle_lib_path() at import time."""

from __future__ import annotations

import os
import sys


def _bootstrap_paddle_paths() -> None:
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        return

    meipass = sys._MEIPASS
    lib_dirs: list[str] = []
    for rel in (
        os.path.join("scipy", ".dylibs"),
        os.path.join("paddle", "libs"),
    ):
        path = os.path.join(meipass, rel)
        if os.path.isdir(path):
            lib_dirs.append(path)

    if not lib_dirs:
        return

    joined = os.pathsep.join(lib_dirs)
    if sys.platform == "darwin":
        prev = os.environ.get("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_LIBRARY_PATH"] = joined + (os.pathsep + prev if prev else "")
    elif os.name == "nt":
        for path in lib_dirs:
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(path)
        prev = os.environ.get("PATH", "")
        os.environ["PATH"] = joined + (os.pathsep + prev if prev else "")
    else:
        prev = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = joined + (os.pathsep + prev if prev else "")

    libs = os.path.join(meipass, "paddle", "libs")

    import site

    original = site.getsitepackages

    def patched_getsitepackages() -> list[str]:
        try:
            dirs = original()
        except Exception:
            dirs = []
        cleaned = [d for d in dirs if d]
        if meipass not in cleaned:
            cleaned.insert(0, meipass)
        return cleaned or [meipass]

    site.getsitepackages = patched_getsitepackages

    if not getattr(site, "USER_SITE", None):
        site.USER_SITE = meipass


_bootstrap_paddle_paths()
