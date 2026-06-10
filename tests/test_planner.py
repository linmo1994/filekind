from pathlib import Path

from filekind.models import AppConfig, FileRecord, ProjectDef, TargetLayout
from filekind.plan.planner import (
    classified_project_count,
    destination_for_record,
    summarize_projects,
)


def test_documents_go_directly_under_project_dir() -> None:
    config = AppConfig(
        projects=[ProjectDef(id="p1", name="会议平板系统", aliases=[], codes=[], description="")],
        target_layout=TargetLayout(
            subdirs_by_extension={
                "images": [".png"],
            }
        ),
    )
    record = FileRecord(
        path="/in/report.pdf",
        filename="report.pdf",
        parent_path="/in",
        extension=".pdf",
        size=1,
        mtime=0.0,
        project_id="p1",
        project_name="会议平板系统",
    )
    dest = destination_for_record(record, Path("/out"), config)
    assert dest == Path("/out/会议平板系统/report.pdf")


def test_images_still_use_subdir() -> None:
    config = AppConfig(
        projects=[ProjectDef(id="p1", name="会议平板系统", aliases=[], codes=[], description="")],
        target_layout=TargetLayout(subdirs_by_extension={"images": [".png"]}),
    )
    record = FileRecord(
        path="/in/logo.png",
        filename="logo.png",
        parent_path="/in",
        extension=".png",
        size=1,
        mtime=0.0,
        project_id="p1",
        project_name="会议平板系统",
    )
    dest = destination_for_record(record, Path("/out"), config)
    assert dest == Path("/out/会议平板系统/images/logo.png")


def test_summarize_projects_counts_and_sorts() -> None:
    records = [
        FileRecord(
            path="/a.pdf",
            filename="a.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="p2",
            project_name="B项目",
        ),
        FileRecord(
            path="/b.pdf",
            filename="b.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="p1",
            project_name="A项目",
        ),
        FileRecord(
            path="/c.pdf",
            filename="c.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="p1",
            project_name="A项目",
        ),
        FileRecord(
            path="/d.pdf",
            filename="d.pdf",
            parent_path="/",
            extension=".pdf",
            size=1,
            mtime=0.0,
            project_id="unclassified",
            project_name="未分类",
        ),
    ]
    stats = summarize_projects(records)
    assert stats[0]["project_name"] == "A项目"
    assert stats[0]["file_count"] == 2
    assert classified_project_count(stats) == 2
