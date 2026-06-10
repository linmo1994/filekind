from __future__ import annotations

import filecmp
from pathlib import Path


def increment_path(path: Path, index: int) -> Path:
    return path.with_name(f"{path.stem} ({index}){path.suffix}")


def unique_on_disk(path: Path) -> Path:
    """Return path if free, otherwise stem (2).ext, stem (3).ext, …"""
    candidate = path
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = increment_path(path, index)
        if not candidate.exists():
            return candidate
        index += 1


def unique_among(path: Path, taken: set[Path]) -> Path:
    """Reserve a destination path unique within the current plan batch."""
    candidate = path.resolve()
    index = 2
    while candidate in taken:
        candidate = increment_path(path, index).resolve()
        index += 1
    taken.add(candidate)
    return candidate


def same_file_content(left: Path, right: Path) -> bool:
    try:
        return filecmp.cmp(left, right, shallow=False)
    except OSError:
        return False
