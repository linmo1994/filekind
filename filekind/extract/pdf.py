from __future__ import annotations

from pathlib import Path

import fitz

from filekind.extract.ocr import ocr_image_bytes
from filekind.models import FileRecord, RuntimeConfig

# 避免 MuPDF 将 GS9 等资源错误直接打印到终端导致用户误以为程序崩溃
fitz.TOOLS.mupdf_display_errors(False)


def _page_text(page: fitz.Page) -> str:
    try:
        text = page.get_text("text") or ""
        return text.strip()
    except Exception:
        return ""


def _page_pixmap_png(page: fitz.Page, *, dpi: int = 150) -> bytes | None:
    """Render page for OCR; some PDFs reference missing ExtGState and fail to rasterize."""
    attempts = [
        {"dpi": dpi, "alpha": False, "annots": False},
        {"matrix": fitz.Matrix(1.5, 1.5), "alpha": False, "annots": False},
    ]
    for kwargs in attempts:
        try:
            pix = page.get_pixmap(**kwargs)
            return pix.tobytes("png")
        except Exception:
            continue
    return None


def _finalize_record(
    record: FileRecord,
    runtime: RuntimeConfig,
    *,
    parts: list[str],
    page_limit: int,
    pages_with_text: int,
    pages_ocrd: int,
    pages_failed: int,
) -> FileRecord:
    snippet = "\n\n".join(parts)
    if len(snippet) > runtime.text_fallback_chars:
        snippet = snippet[: runtime.text_fallback_chars]

    record.raw_snippet = snippet
    record.pages_extracted = page_limit

    if pages_failed and not parts:
        record.extract_method = "pdf_error"
        record.reason = record.reason or "PDF 结构异常，无法提取正文（已跳过该页渲染）"
    elif pages_ocrd and not pages_with_text:
        record.extract_method = "ocr"
    elif pages_ocrd:
        record.extract_method = "pdf_text+ocr"
    elif pages_with_text:
        record.extract_method = "pdf_text"
    else:
        record.extract_method = "metadata_only"
    return record


def extract_pdf(record: FileRecord, runtime: RuntimeConfig) -> FileRecord:
    path = Path(record.path)
    max_pages = runtime.extract_max_pages
    parts: list[str] = []
    pages_with_text = 0
    pages_ocrd = 0
    pages_failed = 0

    try:
        doc = fitz.open(path)
    except Exception:
        record.extract_method = "pdf_error"
        record.pages_extracted = 0
        record.raw_snippet = ""
        record.reason = "无法打开 PDF 文件"
        return record

    page_limit = 0
    try:
        page_limit = min(max_pages, doc.page_count)
        for i in range(page_limit):
            try:
                page = doc.load_page(i)
            except Exception:
                pages_failed += 1
                continue

            page_ok = False
            text = _page_text(page)
            if text:
                pages_with_text += 1
                parts.append(text)
                page_ok = True
            else:
                png = _page_pixmap_png(page)
                if png:
                    ocr_text = ocr_image_bytes(png)
                    if ocr_text:
                        pages_ocrd += 1
                        parts.append(ocr_text)
                        page_ok = True

            if not page_ok:
                pages_failed += 1
    finally:
        doc.close()

    return _finalize_record(
        record,
        runtime,
        parts=parts,
        page_limit=page_limit,
        pages_with_text=pages_with_text,
        pages_ocrd=pages_ocrd,
        pages_failed=pages_failed,
    )
