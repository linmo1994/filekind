from pathlib import Path

from filekind.clerk_report import REPORT_TXT_NAME, write_clerk_reports
from filekind.models import FileRecord


def test_write_clerk_reports(tmp_path: Path) -> None:
    work = tmp_path / "work"
    dest = tmp_path / "已整理"
    dest.mkdir()
    records = [
        FileRecord(
            path=str(tmp_path / "a.pdf"),
            filename="a.pdf",
            parent_path=str(tmp_path),
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="p1",
            project_name="项目甲",
            confidence=0.9,
            classified_by="rule",
            reason="命中编号",
        ),
        FileRecord(
            path=str(tmp_path / "b.pdf"),
            filename="b.pdf",
            parent_path=str(tmp_path),
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="unclassified",
            project_name="未分类",
            confidence=0.0,
            classified_by="none",
            reason="无法识别",
        ),
    ]
    txt_path, xlsx_path = write_clerk_reports(
        work,
        records,
        dest_root=dest,
        inventory_path=None,
        inventory_project_count=0,
    )
    assert txt_path == work / REPORT_TXT_NAME
    assert txt_path.is_file()
    text = txt_path.read_text(encoding="utf-8")
    assert "项目甲" in text
    assert "未分类" in text
    assert xlsx_path is not None and xlsx_path.is_file()
    copies = list(tmp_path.glob("整理结果-*.txt"))
    assert len(copies) == 1
