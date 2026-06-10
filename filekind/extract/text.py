from __future__ import annotations

from pathlib import Path

from filekind.models import FileRecord, RuntimeConfig


def extract_plain_text(record: FileRecord, runtime: RuntimeConfig) -> FileRecord:
    path = Path(record.path)
    max_chars = runtime.text_fallback_chars
    max_lines = 150
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        record.extract_method = "metadata_only"
        return record

    lines = text.splitlines()
    if len(lines) > max_lines:
        text = "\n".join(lines[:max_lines])
    record.raw_snippet = text[:max_chars]
    record.pages_extracted = 1
    record.extract_method = "text"
    return record
