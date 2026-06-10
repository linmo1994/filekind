from __future__ import annotations

import hashlib
from pathlib import Path

from filekind.models import FileRecord, resolve_path


SKIP_DIR_NAMES = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "node_modules",
    ".Trash",
    ".DS_Store",
}


def _should_skip_file(path: Path) -> bool:
    name = path.name
    if name in {".DS_Store", "Thumbs.db", "desktop.ini"}:
        return True
    # Excel/Office 打开文件时产生的临时锁文件，不是有效文档
    if name.startswith("~$") or name.startswith(".~"):
        return True
    return False


class EmptyInboxError(ValueError):
    """Raised when the source directory contains no files to organize."""


def count_files_in_directory(source: Path, *, max_files: int) -> int:
    source = resolve_path(source)
    if not source.is_dir():
        raise ValueError(f"Source is not a directory: {source}")
    count = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if _should_skip_file(path):
            continue
        count += 1
        if count >= max_files:
            break
    return count


def _file_md5(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def scan_directory(
    source: Path,
    *,
    max_files: int,
    compute_md5: bool = False,
) -> list[FileRecord]:
    source = resolve_path(source)
    if not source.is_dir():
        raise ValueError(f"Source is not a directory: {source}")

    records: list[FileRecord] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if _should_skip_file(path):
            continue
        stat = path.stat()
        record = FileRecord(
            path=str(path),
            filename=path.name,
            parent_path=str(path.parent),
            extension=path.suffix.lower(),
            size=stat.st_size,
            mtime=stat.st_mtime,
        )
        if compute_md5:
            record.md5 = _file_md5(path)
        records.append(record)
        if len(records) >= max_files:
            break
    if not records:
        raise EmptyInboxError(
            f"待整理目录为空，没有可处理的文件: {source}\n"
            "请先将文件放入该目录后再运行。"
        )
    return records
