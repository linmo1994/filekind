from __future__ import annotations

from pathlib import Path

from filekind.extract.ocr import ocr_image_file
from filekind.models import FileRecord, RuntimeConfig


def extract_image(record: FileRecord, runtime: RuntimeConfig) -> FileRecord:
    text = ocr_image_file(Path(record.path))
    record.raw_snippet = (text or "")[: runtime.text_fallback_chars]
    record.pages_extracted = 1
    record.extract_method = "ocr" if text else "metadata_only"
    return record
