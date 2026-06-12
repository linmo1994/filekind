from filekind.classify.report import classified_count, format_llm_result_line
from filekind.models import FileRecord


def test_classified_count_respects_threshold() -> None:
    records = [
        FileRecord(
            path="/a.pdf",
            filename="a.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="p1",
            project_name="项目甲",
            confidence=0.9,
        ),
        FileRecord(
            path="/b.pdf",
            filename="b.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="unclassified",
            project_name="未分类",
            confidence=0.0,
        ),
    ]
    assert classified_count(records, 0.65) == 1


def test_format_llm_result_line() -> None:
    record = FileRecord(
        path="/a.pdf",
        filename="a.pdf",
        parent_path="/",
        extension=".pdf",
        size=1,
        mtime=0.0,
        project_id="p1",
        project_name="CV352系统",
        confidence=0.82,
    )
    assert "CV352系统" in format_llm_result_line(record, 0.65)
    assert "0.82" in format_llm_result_line(record, 0.65)
