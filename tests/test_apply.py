from pathlib import Path

from filekind.apply.executor import apply_plan, rollback
from filekind.models import MovePlanEntry


def test_apply_skips_when_destination_has_same_file(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out" / "proj"
    src_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)

    content = b"same pdf content"
    src = src_dir / "report.pdf"
    dest = dest_dir / "report.pdf"
    src.write_bytes(content)
    dest.write_bytes(content)

    plan = [
        MovePlanEntry(
            source=str(src),
            destination=str(dest),
            project_id="unclassified",
            project_name="未分类",
            confidence=0.0,
            classified_by="none",
            matched_by=None,
            reason="",
        )
    ]

    result = apply_plan(plan, manifest_path=tmp_path / "manifest.json", dry_run=False)

    assert src.exists()
    assert dest.exists()
    assert len(result.copied) == 0
    assert len(result.skipped) == 1


def test_apply_renames_when_destination_exists_with_different_content(
    tmp_path: Path,
) -> None:
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out" / "proj"
    src_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)

    src = src_dir / "report.pdf"
    dest = dest_dir / "report.pdf"
    src.write_bytes(b"new content")
    dest.write_bytes(b"old content")

    plan = [
        MovePlanEntry(
            source=str(src),
            destination=str(dest),
            project_id="unclassified",
            project_name="未分类",
            confidence=0.0,
            classified_by="none",
            matched_by=None,
            reason="",
        )
    ]

    result = apply_plan(plan, manifest_path=tmp_path / "manifest.json", dry_run=False)

    assert src.exists()
    assert dest.exists()
    renamed = dest_dir / "report (2).pdf"
    assert renamed.exists()
    assert renamed.read_bytes() == b"new content"
    assert len(result.copied) == 1


def test_rollback_removes_copy_keeps_source(tmp_path: Path) -> None:
    src_dir = tmp_path / "in"
    dest_dir = tmp_path / "out" / "proj"
    src_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)

    src = src_dir / "report.pdf"
    dest = dest_dir / "report.pdf"
    src.write_bytes(b"content")

    plan = [
        MovePlanEntry(
            source=str(src),
            destination=str(dest),
            project_id="unclassified",
            project_name="未分类",
            confidence=0.0,
            classified_by="none",
            matched_by=None,
            reason="",
        )
    ]
    manifest = tmp_path / "manifest.json"
    apply_plan(plan, manifest_path=manifest, dry_run=False)

    assert src.exists()
    assert dest.exists()

    count = rollback(manifest, dry_run=False)
    assert count == 1
    assert src.exists()
    assert not dest.exists()
