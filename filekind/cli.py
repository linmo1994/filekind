from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from filekind.apply.executor import ApplyError, apply_plan, rollback
from filekind.clerk_report import REPORT_TXT_NAME
from filekind.config import (
    ConfigNotFoundError,
    InventoryNotFoundError,
    RunPathsError,
    config_not_found_hint,
    load_config,
    resolve_config_path,
    resolve_inventory_path,
    resolve_run_paths,
)
from filekind.inventory import InventoryError, load_projects_from_inventory
from filekind.inventory_picker import discover_inventory_candidates, resolve_inventory_for_run
from filekind.pipeline import run_pipeline
from filekind.scan.scanner import EmptyInboxError
from filekind.plan.planner import classified_project_count, load_plan, summarize_moves
from filekind.run_summary import print_run_summary
from filekind.extract.ocr import ocr_status_message
from filekind.prompts import load_classify_prompts, resolve_classify_prompts_path

app = typer.Typer(
    name="filekind",
    help="按软件/系统项目整理本地文件（规则 + 向量关联 + 可选本地 LLM）",
    no_args_is_help=True,
)


def _open_in_file_manager(path: Path) -> None:
    import subprocess
    import sys

    target = path.resolve()
    if not target.exists():
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=False)
    elif sys.platform == "win32":
        subprocess.run(["explorer", str(target)], check=False)
    else:
        subprocess.run(["xdg-open", str(target)], check=False)


def _confirm_copy(*, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = typer.confirm("是否复制到已整理目录？", default=True)
    except typer.Abort:
        return False
    return bool(answer)


def _resolve_projects(projects: Optional[Path]) -> Path:
    try:
        return resolve_config_path(projects)
    except ConfigNotFoundError as exc:
        typer.echo(config_not_found_hint(exc), err=True)
        raise typer.Exit(code=1) from exc


def _load_plan_meta(plan_path: Path) -> dict:
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    return data.get("meta") or {}


def _ensure_plan_meta_with_stats(
    meta: dict, moves: list | None = None
) -> dict:
    if meta.get("project_stats"):
        return meta
    if not moves:
        return meta

    stats = summarize_moves(moves)
    file_count = int(meta.get("file_count") or 0)
    unclassified = meta.get("unclassified_file_count")
    if unclassified is None:
        unclassified = max(0, file_count - len(moves)) if file_count else 0

    return {
        **meta,
        "project_stats": stats,
        "classified_project_count": classified_project_count(stats),
        "unclassified_file_count": int(unclassified or 0),
    }


def _relative_to_source(path: str | Path, source: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(source.resolve()))
    except ValueError:
        return str(path)


def _print_extract_summary(
    records: list,
    source_path: Path,
    *,
    work_dir: Path | None = None,
) -> None:
    pdf_records = [r for r in records if (r.extension or "").lower() == ".pdf"]
    pdf_errors = [r for r in records if r.extract_method == "pdf_error"]
    if not pdf_records and not pdf_errors:
        return

    typer.echo("")
    typer.echo("提取摘要")
    if pdf_records:
        typer.echo(f"  PDF 总数: {len(pdf_records)}")
    if pdf_errors:
        typer.echo(
            f"  无法提取正文: {len(pdf_errors)} 个"
            "（仍会按文件名、路径与分类模型处理，整理照常进行）"
        )
        for item in pdf_errors[:10]:
            rel = _relative_to_source(item.path, source_path)
            reason = item.extract_reason or item.reason or "PDF 无法提取正文"
            typer.echo(f"    - {rel}  ({reason})")
        if len(pdf_errors) > 10:
            typer.echo(f"    … 另有 {len(pdf_errors) - 10} 个")
        if work_dir is not None:
            report = work_dir / "pdf_extract_issues.json"
            if report.is_file():
                typer.echo(f"  完整清单: {report}")


def _print_final_summary(plan_meta: dict) -> None:
    print_run_summary(plan_meta, echo=typer.echo, title="整理汇总")


@app.command("run")
def run_cmd(
    source: Optional[Path] = typer.Argument(
        None,
        help="待整理目录（默认 projects.yaml → paths.source）",
    ),
    dest: Optional[Path] = typer.Argument(
        None,
        help="整理输出根目录（默认 projects.yaml → paths.dest）",
    ),
    projects: Optional[Path] = typer.Option(
        None,
        "--projects",
        "-p",
        help="配置文件（默认自动查找 projects.yaml）",
    ),
    work_dir: Optional[Path] = typer.Option(
        None,
        "--work-dir",
        help="计划与报告输出目录（默认 ./filekind-work/<timestamp>）",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="分类后直接复制到已整理目录（默认仅生成 plan.json）",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="apply 时是否仅预览；run 默认总是先生成计划",
    ),
    inventory: Optional[Path] = typer.Option(
        None,
        "--inventory",
        "-i",
        help="项目清单 Excel（默认自动识别或交互选择）",
    ),
    pick_inventory: Optional[bool] = typer.Option(
        None,
        "--pick-inventory/--no-pick-inventory",
        help="自动识别/选择项目清单 Excel（默认在终端交互时开启）",
    ),
    confirm: bool = typer.Option(
        False,
        "--confirm",
        help="复制前先展示整理计划并确认（推荐文员使用）",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="跳过复制确认（与 --confirm 联用时直接复制）",
    ),
    open_dest: bool = typer.Option(
        False,
        "--open-dest",
        help="复制完成后打开已整理目录",
    ),
) -> None:
    """扫描 → 提取前3页 → 分类 → 生成 plan.json"""
    config_path = _resolve_projects(projects)
    config = load_config(explicit=config_path)
    try:
        source_path, dest_path = resolve_run_paths(
            config_path, config, source, dest
        )
    except RunPathsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    interactive_inventory = (
        pick_inventory if pick_inventory is not None else sys.stdin.isatty()
    )
    pipeline_apply = apply and not confirm

    if apply and config.runtime.dry_run_by_default and dry_run and pipeline_apply:
        typer.echo("提示: 使用 --apply --no-dry-run 才会复制文件到已整理目录")

    def progress(message: str) -> None:
        typer.echo(message)

    apply_result = None
    try:
        records, plan_path, apply_result = run_pipeline(
            source=source_path,
            dest=dest_path,
            config_path=config_path,
            work_dir=work_dir,
            apply_moves=pipeline_apply,
            dry_run=dry_run,
            inventory=inventory,
            interactive_inventory=interactive_inventory,
            on_progress=progress,
        )
    except EmptyInboxError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (InventoryNotFoundError, InventoryError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except ApplyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"配置文件: {config_path}")
    typer.echo(f"待整理: {source_path}")
    typer.echo(f"输出目录: {dest_path}")

    plan_meta = _load_plan_meta(plan_path)
    inv_path = plan_meta.get("inventory_excel")
    if inv_path:
        typer.echo(
            f"项目清单: {inv_path}（共 {plan_meta.get('inventory_project_count', '?')} 个项目，清单文件不参与整理）"
        )
    typer.echo(f"已处理 {len(records)} 个文件")

    _print_extract_summary(records, source_path, work_dir=plan_path.parent)

    typer.echo(f"计划已写入: {plan_path}")
    summary_path = plan_path.parent / "summary.json"
    if summary_path.is_file():
        typer.echo(f"统计详情已写入: {summary_path}")
    clerk_txt = plan_path.parent / REPORT_TXT_NAME
    if clerk_txt.is_file():
        typer.echo(f"整理结果报告: {clerk_txt}")

    copied = False
    if apply and confirm:
        should_copy = yes or _confirm_copy(assume_yes=False)
        if not should_copy:
            typer.echo("")
            typer.echo("已取消复制。待整理原文件未改动。")
            typer.echo(f"若确认无误，可执行: filekind apply {plan_path} --no-dry-run")
            raise typer.Exit(code=0)
        try:
            from filekind.plan.planner import load_plan

            moves, _ = load_plan(plan_path)
            manifest_path = plan_path.parent / "manifest.json"
            apply_result = apply_plan(moves, manifest_path=manifest_path, dry_run=False)
            copied = True
        except ApplyError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    if apply and not dry_run and apply_result is not None:
        typer.echo(f"已复制 {len(apply_result.copied)} 个文件到已整理目录（待整理原文件保留）")
        typer.echo(f"复制清单: {plan_path.parent / 'manifest.json'}")
        if apply_result.skipped:
            typer.echo(f"跳过 {len(apply_result.skipped)} 个:", err=True)
            for line in apply_result.skipped[:10]:
                typer.echo(f"  - {line}", err=True)
            if len(apply_result.skipped) > 10:
                typer.echo(f"  … 另有 {len(apply_result.skipped) - 10} 个", err=True)
        copied = True
        if open_dest:
            _open_in_file_manager(dest_path)

    if copied or not apply:
        _print_final_summary(_ensure_plan_meta_with_stats(plan_meta))


@app.command("apply")
def apply_cmd(
    plan_file: Path = typer.Argument(..., help="plan.json 路径"),
    manifest: Optional[Path] = typer.Option(
        None,
        "--manifest",
        "-m",
        help="复制清单输出路径（默认与 plan 同目录 manifest.json）",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="仅校验不复制",
    ),
) -> None:
    """根据 plan.json 将文件复制到目标目录（不改动待整理原文件）"""
    moves, meta = load_plan(plan_file)
    manifest_path = manifest or (plan_file.parent / "manifest.json")
    try:
        result = apply_plan(moves, manifest_path=manifest_path, dry_run=dry_run)
    except ApplyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if dry_run:
        typer.echo(f"校验通过，将复制 {len(moves)} 个文件（dry-run，待整理原文件保留）")
    else:
        typer.echo(f"已复制 {len(result.copied)} 个文件")
        typer.echo(f"清单: {manifest_path}")
        if result.skipped:
            typer.echo(f"跳过 {len(result.skipped)} 个:", err=True)
            for line in result.skipped[:10]:
                typer.echo(f"  - {line}", err=True)
        _print_final_summary(_ensure_plan_meta_with_stats(meta, moves))


@app.command("rollback")
def rollback_cmd(
    manifest_file: Path = typer.Argument(..., help="manifest.json 路径"),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="仅预览回滚",
    ),
) -> None:
    """根据 manifest.json 删除已整理目录中的副本（待整理原文件不受影响）"""
    try:
        count = rollback(manifest_file, dry_run=dry_run)
    except ApplyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    if dry_run:
        typer.echo(f"将删除 {count} 个已整理副本（dry-run）")
    else:
        typer.echo(f"已删除 {count} 个已整理副本")


@app.command("summary")
def summary_cmd(
    plan_file: Path = typer.Argument(..., help="plan.json 或 summary.json 路径"),
) -> None:
    """查看某次整理的分类统计"""
    path = plan_file.resolve()
    if path.name == "summary.json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = {
            "classified_project_count": payload.get("classified_project_count", 0),
            "unclassified_file_count": payload.get("unclassified_file_count", 0),
            "project_stats": payload.get("projects") or [],
        }
    else:
        moves, meta = load_plan(path)
        meta = _ensure_plan_meta_with_stats(meta, moves)
    _print_final_summary(meta)


@app.command("validate-config")
def validate_config_cmd(
    projects: Optional[Path] = typer.Option(
        None,
        "--projects",
        "-p",
        help="配置文件（默认自动查找 projects.yaml）",
    ),
) -> None:
    """校验 projects.yaml"""
    config_path = _resolve_projects(projects)
    config = load_config(explicit=config_path)
    typer.echo(f"配置文件: {config_path}")
    src: Path | None = None
    try:
        src, dst = resolve_run_paths(config_path, config, None, None)
        typer.echo(f"默认待整理: {src}")
        typer.echo(f"默认输出: {dst}")
    except RunPathsError as exc:
        typer.echo(f"默认待整理: {config.paths.source} (目录尚未创建)")
        typer.echo(f"默认输出: {config.paths.dest}")
        typer.echo(f"提示: {exc}", err=True)

    inventory_setting = (config.paths.inventory_excel or "").strip()

    if src is not None:
        typer.echo("项目清单 Excel:")
        candidates = discover_inventory_candidates(config_path, src)
        if candidates:
            for path, count in candidates[:10]:
                typer.echo(f"  - {path.name}（{count} 个项目）  {path}")
            if len(candidates) > 10:
                typer.echo(f"  … 另有 {len(candidates) - 10} 个候选")
        else:
            typer.echo("  未在 待整理/ 或 项目清单/ 中发现可用清单")
        if inventory_setting:
            typer.echo(f"  配置指定: {inventory_setting}")
        try:
            inventory_path = resolve_inventory_for_run(
                config_path,
                config,
                src,
                interactive=False,
            )
            project_list = load_projects_from_inventory(inventory_path)
            typer.echo(f"  将使用: {inventory_path.name}（{len(project_list)} 个项目）")
        except (InventoryNotFoundError, InventoryError) as exc:
            typer.echo(f"  清单: {exc}", err=True)
    else:
        typer.echo("项目清单 Excel: 请先创建待整理目录后再校验")

    typer.echo(f"hardware_profile: {config.hardware_profile}")
    typer.echo(f"embedding: {config.models.embedding}")
    typer.echo(f"llm_gguf: {config.models.llm_gguf or '(未配置，跳过 LLM)'}")
    typer.echo(f"OCR: {ocr_status_message()}")

    prompt_setting = (config.paths.classify_prompts or "classify_prompts.txt").strip()
    typer.echo(f"分类提示词: {prompt_setting}")
    prompt_path = resolve_classify_prompts_path(config_path, config)
    if prompt_path is None:
        typer.echo("  未找到提示词文件，将使用内置默认提示词")
        typer.echo("  可复制 classify_prompts.example.txt 为 classify_prompts.txt 后修改（纯文本，无需 YAML）")
    else:
        prompts = load_classify_prompts(config_path, config)
        typer.echo(f"  已加载: {prompt_path}")
        if prompts.source_path is not None:
            typer.echo("  修改该文件即可调整 LLM 分类规则与说明")


if __name__ == "__main__":
    app()
