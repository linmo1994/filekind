from pathlib import Path

import pytest

from filekind.scan.scanner import EmptyInboxError, scan_directory


def test_empty_inbox_raises(tmp_path: Path) -> None:
    inbox = tmp_path / "待整理"
    inbox.mkdir()
    with pytest.raises(EmptyInboxError, match="待整理目录为空"):
        scan_directory(inbox, max_files=100)


def test_non_empty_inbox_ok(tmp_path: Path) -> None:
    inbox = tmp_path / "待整理"
    inbox.mkdir()
    (inbox / "a.txt").write_text("hello", encoding="utf-8")
    records = scan_directory(inbox, max_files=100)
    assert len(records) == 1
