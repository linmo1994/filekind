from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from filekind.classify import classify_records
from filekind.config import default_work_dir, load_config
from filekind.inventory_picker import resolve_inventory_for_run
from filekind.extract import extract_text
from filekind.extract.ocr import (
    ocr_status_message,
    release_ocr,
    set_ocr_progress_callback,
)
from filekind.inventory import InventoryError, load_projects_from_inventory
from filekind.models import AppConfig, FileRecord
from filekind.plan.planner import build_plan, summarize_projects, write_files_jsonl, write_plan
from filekind.clerk_report import write_clerk_reports
from filekind.run_summary import inventory_projects_payload
from filekind.scan.scanner import EmptyInboxError, scan_directory

ProgressFn = Callable[[str], None]


def _relative_to_source(path: str | Path, source: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(source.resolve()))
    except ValueError:
        return str(path)


def write_pdf_extract_issues(
    work: Path,
    records: list[FileRecord],
    *,
    source: Path,
) -> Path | None:
    issues = [
        {
            "path": _relative_to_source(record.path, source),
            "filename": record.filename,
            "reason": record.extract_reason or record.reason or "PDF 无法提取正文",
            "extract_method": record.extract_method,
        }
        for record in records
        if record.extract_method == "pdf_error"
    ]
    if not issues:
        return None
    report_path = work / "pdf_extract_issues.json"
    report_path.write_text(
        json.dumps(
            {"count": len(issues), "files": issues},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_path


def run_pipeline(
    *,
    source: Path,
    dest: Path,
    config_path: Path,
    work_dir: Optional[Path] = None,
    apply_moves: bool = False,
    dry_run: bool = True,
    inventory: Optional[Path] = None,
    interactive_inventory: bool = True,
    on_progress: ProgressFn | None = None,
) -> tuple[list[FileRecord], Path, "ApplyResult | None"]:
    def say(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    config = load_config(config_path)
    inventory_path = resolve_inventory_for_run(
        config_path,
        config,
        source,
        explicit=inventory,
        interactive=interactive_inventory,
        on_message=say,
    )

    say("扫描待整理目录…")
    records = scan_directory(
        source,
        max_files=config.runtime.max_files_per_run,
        compute_md5=False,
    )

    inventory_projects: list | None = None
    if inventory_path is not None:
        inventory_projects = load_projects_from_inventory(inventory_path)
        config = AppConfig(
            hardware_profile=config.hardware_profile,
            runtime=config.runtime,
            code_patterns=list(config.code_patterns),
            models=config.models,
            target_layout=config.target_layout,
            paths=config.paths,
            projects=inventory_projects,
        )
        inv_resolved = inventory_path.resolve()
        records = [r for r in records if Path(r.path).resolve() != inv_resolved]

    if not records:
        raise EmptyInboxError(
            f"除项目清单外没有可处理的文件: {source}\n"
            "请放入待整理文件后再运行（清单 Excel 本身不会被移动）。"
        )

    total = len(records)
    say(f"共 {total} 个文件待处理（不含项目清单）")

    say("提取正文（每文件前 3 页）…")
    say(f"  {ocr_status_message()}")
    set_ocr_progress_callback(say)
    try:
        for index, record in enumerate(records):
            done = index + 1
            say(f"  提取 {done}/{total}：{record.filename}")
            records[index] = extract_text(record, config.runtime)
    finally:
        set_ocr_progress_callback(None)
        release_ocr()

    pdf_errors = sum(1 for record in records if record.extract_method == "pdf_error")
    if pdf_errors:
        say(
            f"  其中 {pdf_errors} 个 PDF 未能提取正文"
            "（仍会用文件名、路径与分类模型继续处理）"
        )

    say("分类（规则 → 向量关联 → 可选 LLM）…")
    records = classify_records(
        records,
        config,
        config_path=config_path,
        on_progress=on_progress,
    )
    say("分类完成")

    plan = build_plan(
        records,
        source_root=source,
        dest_root=dest,
        config=config,
    )

    project_stats = summarize_projects(records)
    classified_count = sum(
        1 for row in project_stats if row["project_id"] != "unclassified"
    )
    unclassified_count = sum(
        row["file_count"]
        for row in project_stats
        if row["project_id"] == "unclassified"
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = work_dir or default_work_dir(config_path, run_id)
    work.mkdir(parents=True, exist_ok=True)

    plan_path = work / "plan.json"
    summary_meta = {
        "inventory_project_count": len(inventory_projects or config.projects),
        "inventory_projects": inventory_projects_payload(
            inventory_projects or config.projects
        ),
        "file_count": len(records),
        "classified_project_count": classified_count,
        "unclassified_file_count": unclassified_count,
        "project_stats": project_stats,
    }
    write_plan(
        plan_path,
        plan,
        meta={
            "source": str(source.resolve()),
            "dest": str(dest.resolve()),
            "config": str(config_path.resolve()),
            "inventory_excel": str(inventory_path.resolve()) if inventory_path else None,
            **summary_meta,
            "move_count": len(plan),
        },
    )
    summary_path = work / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "classified_project_count": classified_count,
                "unclassified_file_count": unclassified_count,
                "total_files": len(records),
                "projects": project_stats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_files_jsonl(work / "files.jsonl", records)
    issues_path = write_pdf_extract_issues(work, records, source=source)
    if issues_path is not None:
        say(f"PDF 提取问题清单: {issues_path}")

    txt_report, xlsx_report = write_clerk_reports(
        work,
        records,
        dest_root=dest,
        inventory_path=inventory_path,
        inventory_project_count=len(inventory_projects or config.projects),
        summary_meta=summary_meta,
    )
    say(f"整理结果报告: {txt_report}")
    if xlsx_report is not None:
        say(f"Excel 报告: {xlsx_report}")

    if apply_moves and not dry_run:
        from filekind.apply.executor import apply_plan

        say("复制到已整理目录…")
        manifest_path = work / "manifest.json"
        apply_result = apply_plan(plan, manifest_path=manifest_path, dry_run=False)
        say(f"已复制 {len(apply_result.copied)} 个文件")
    else:
        apply_result = None

    return records, plan_path, apply_result
