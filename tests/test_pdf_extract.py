from pathlib import Path
from unittest.mock import MagicMock, patch

from filekind.extract.pdf import extract_pdf
from filekind.models import FileRecord, RuntimeConfig


def test_open_pdf_failure_returns_metadata(tmp_path: Path) -> None:
    record = FileRecord(
        path=str(tmp_path / "bad.pdf"),
        filename="bad.pdf",
        parent_path=str(tmp_path),
        extension=".pdf",
        size=1,
        mtime=0.0,
    )
    runtime = RuntimeConfig()
    with patch("filekind.extract.pdf.fitz.open", side_effect=RuntimeError("MuPDF error")):
        result = extract_pdf(record, runtime)
    assert result.extract_method == "pdf_error"
    assert result.raw_snippet == ""


def test_page_render_failure_does_not_raise(tmp_path: Path) -> None:
    record = FileRecord(
        path=str(tmp_path / "x.pdf"),
        filename="x.pdf",
        parent_path=str(tmp_path),
        extension=".pdf",
        size=1,
        mtime=0.0,
    )
    runtime = RuntimeConfig()

    page = MagicMock()
    page.get_text.return_value = ""
    page.get_pixmap.side_effect = RuntimeError("cannot find ExtGState resource 'GS9'")

    doc = MagicMock()
    doc.page_count = 1
    doc.load_page.return_value = page

    with patch("filekind.extract.pdf.fitz.open", return_value=doc):
        result = extract_pdf(record, runtime)

    assert result.extract_method in {"pdf_error", "metadata_only"}
    doc.close.assert_called_once()
