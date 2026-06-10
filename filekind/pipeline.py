from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from filekind.classify import classify_records
from filekind.config import InventoryNotFoundError, load_config, resolve_inventory_path
from filekind.extract import extract_text
from filekind.extract.ocr import release_ocr
from filekind.inventory import InventoryError, load_projects_from_inventory
from filekind.models import AppConfig, FileRecord
from filekind.plan.planner import build_plan, summarize_projects, write_files_jsonl, write_plan
from filekind.scan.scanner import EmptyInboxError, scan_directory


def run_pipeline(
    *,
    source: Path,
    dest: Path,
    config_path: Path,
    work_dir: Optional[Path] = None,
    apply_moves: bool = False,
    dry_run: bool = True,
    inventory: Optional[Path] = None,
) -> tuple[list[FileRecord], Path, "ApplyResult | None"]:
    config = load_config(config_path)
    inventory_path = resolve_inventory_path(
        config_path, config, source, explicit=inventory
    )

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

    for index, record in enumerate(records):
        records[index] = extract_text(record, config.runtime)

    release_ocr()

    records = classify_records(records, config, config_path=config_path)

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
    work = work_dir or (Path.cwd() / "filekind-work" / run_id)
    work.mkdir(parents=True, exist_ok=True)

    plan_path = work / "plan.json"
    write_plan(
        plan_path,
        plan,
        meta={
            "source": str(source.resolve()),
            "dest": str(dest.resolve()),
            "config": str(config_path.resolve()),
            "inventory_excel": str(inventory_path.resolve()) if inventory_path else None,
            "inventory_project_count": len(inventory_projects or config.projects),
            "file_count": len(records),
            "move_count": len(plan),
            "classified_project_count": classified_count,
            "unclassified_file_count": unclassified_count,
            "project_stats": project_stats,
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

    if apply_moves and not dry_run:
        from filekind.apply.executor import apply_plan

        manifest_path = work / "manifest.json"
        apply_result = apply_plan(plan, manifest_path=manifest_path, dry_run=False)
    else:
        apply_result = None

    return records, plan_path, apply_result
