from __future__ import annotations

from pathlib import Path

import sys

import pytest

from filekind.frozen_entry import prepare_windows_frozen_default_argv


def test_prepare_windows_frozen_default_argv_injects_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv = ["filekind.exe"]
    assert prepare_windows_frozen_default_argv(argv) is False

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "win32")

    argv = ["C:\\dist\\filekind.exe"]
    assert prepare_windows_frozen_default_argv(argv) is True
    assert argv[1:] == [
        "run",
        "--apply",
        "--no-dry-run",
        "--confirm",
        "--open-dest",
    ]
    assert prepare_windows_frozen_default_argv(["filekind.exe", "--help"]) is False


def test_run_filekind_bat_avoids_internal_backslash_quote() -> None:
    bat = Path(__file__).resolve().parents[1] / "scripts" / "run-filekind.bat"
    content = bat.read_text(encoding="utf-8")
    assert '_internal\\"' not in content
