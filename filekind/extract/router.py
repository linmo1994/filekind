from __future__ import annotations

from pathlib import Path

from filekind.extract.image import extract_image
from filekind.extract.office import extract_docx, extract_pptx, extract_xlsx
from filekind.extract.pdf import extract_pdf
from filekind.extract.text import extract_plain_text
from filekind.models import FileRecord, RuntimeConfig


def extract_for_record(record: FileRecord, runtime: RuntimeConfig) -> FileRecord:
    path = Path(record.path)
    ext = record.extension

    if ext == ".pdf":
        return extract_pdf(record, runtime)
    if ext in {".docx"}:
        return extract_docx(record, runtime)
    if ext in {".pptx"}:
        return extract_pptx(record, runtime)
    if ext in {".xlsx", ".xlsm"}:
        return extract_xlsx(record, runtime)
    if ext in {
        ".txt",
        ".md",
        ".markdown",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".go",
        ".rs",
        ".sql",
        ".html",
        ".xml",
    }:
        return extract_plain_text(record, runtime)
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}:
        return extract_image(record, runtime)

    record.extract_method = "metadata_only"
    record.pages_extracted = 0
    record.raw_snippet = ""
    return record
