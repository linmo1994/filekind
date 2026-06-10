from __future__ import annotations

from filekind.models import FileRecord, RuntimeConfig


def truncate_snippet(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def extract_text(record: FileRecord, runtime: RuntimeConfig) -> FileRecord:
    from filekind.extract.router import extract_for_record

    return extract_for_record(record, runtime)
