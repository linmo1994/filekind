from pathlib import Path

from filekind.extract.office import extract_xlsx
from filekind.models import FileRecord, RuntimeConfig
from filekind.scan.scanner import scan_directory


def test_scan_skips_office_temp_files(tmp_path: Path) -> None:
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "report.xlsx").write_bytes(b"not a zip")
    (inbox / ".~report.xlsx").write_bytes(b"temp")
    (inbox / "~$report.xlsx").write_bytes(b"lock")
    (inbox / "ok.txt").write_text("hello", encoding="utf-8")

    records = scan_directory(inbox, max_files=100)
    names = {r.filename for r in records}
    assert names == {"report.xlsx", "ok.txt"}


def test_xlsx_extract_error_does_not_raise(tmp_path: Path) -> None:
    path = tmp_path / "bad.xlsx"
    path.write_bytes(b"not a zip")
    record = FileRecord(
        path=str(path),
        filename=path.name,
        parent_path=str(tmp_path),
        extension=".xlsx",
        size=path.stat().st_size,
        mtime=0.0,
    )
    result = extract_xlsx(record, RuntimeConfig())
    assert result.extract_method == "xlsx_error"
    assert result.raw_snippet == ""
