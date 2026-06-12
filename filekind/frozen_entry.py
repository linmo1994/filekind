"""PyInstaller / frozen executable entry helpers."""

from __future__ import annotations

import os
import sys


def prepare_windows_frozen_default_argv(argv: list[str] | None = None) -> bool:
    """Double-clicking filekind.exe on Windows should run the clerk workflow."""
    target = sys.argv if argv is None else argv
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform != "win32":
        return False
    if len(target) > 1:
        return False
    target.extend(["run", "--apply", "--no-dry-run", "--confirm", "--open-dest"])
    return True


def run_app() -> int:
    from filekind.cli import app

    try:
        app()
    except SystemExit as exc:
        code = exc.code
        if not isinstance(code, int):
            code = 1 if code else 0
        return code
    return 0


def maybe_pause_after_auto_clerk(*, auto_clerk: bool) -> None:
    if not auto_clerk or os.environ.get("FILEKIND_FROM_BAT"):
        return
    try:
        input("\n按 Enter 键退出...")
    except EOFError:
        pass
