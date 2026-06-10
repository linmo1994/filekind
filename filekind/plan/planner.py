from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from filekind.models import AppConfig, FileRecord, MoveManifestEntry, MovePlanEntry, resolve_path
from filekind.path_utils import unique_among


def _subdir_for_extension(config: AppConfig, extension: str) -> str:
    layout = config.target_layout.subdirs_by_extension
    for subdir, extensions in layout.items():
        if extension.lower() in {e.lower() for e in extensions}:
            return subdir
    return ""


def destination_for_record(record: FileRecord, dest_root: Path, config: AppConfig) -> Path:
    project_id = record.project_id or "unclassified"
    if project_id == "unclassified":
        project_dir = config.target_layout.unclassified_dir
    else:
        project = next((p for p in config.projects if p.id == project_id), None)
        project_dir = project.name if project else project_id

    subdir = _subdir_for_extension(config, record.extension)
    base = dest_root / project_dir
    if subdir:
        return base / subdir / record.filename
    return base / record.filename


def build_plan(
    records: list[FileRecord],
    *,
    source_root: Path,
    dest_root: Path,
    config: AppConfig,
) -> list[MovePlanEntry]:
    source_root = resolve_path(source_root)
    dest_root = resolve_path(dest_root)
    plan: list[MovePlanEntry] = []
    reserved_dests: set[Path] = set()

    for record in records:
        src = Path(record.path)
        if not src.exists():
            continue
        dest = destination_for_record(record, dest_root, config)
        if src.resolve() == dest.resolve():
            continue
        dest = unique_among(dest, reserved_dests)
        plan.append(
            MovePlanEntry(
                source=str(src),
                destination=str(dest),
                project_id=record.project_id or "unclassified",
                project_name=record.project_name or "未分类",
                confidence=record.confidence,
                classified_by=record.classified_by or "none",
                matched_by=record.matched_by,
                reason=record.reason,
            )
        )
    return plan


def summarize_projects(records: list[FileRecord]) -> list[dict[str, int | str]]:
    """Count files per classified project (includes unclassified bucket)."""
    counts: dict[tuple[str, str], int] = {}
    for record in records:
        project_id = record.project_id or "unclassified"
        project_name = record.project_name or "未分类"
        key = (project_id, project_name)
        counts[key] = counts.get(key, 0) + 1

    rows = [
        {"project_id": pid, "project_name": pname, "file_count": count}
        for (pid, pname), count in counts.items()
    ]
    rows.sort(key=lambda row: (-int(row["file_count"]), str(row["project_name"])))
    return rows


def summarize_moves(moves: list[MovePlanEntry]) -> list[dict[str, int | str]]:
    """Derive per-project counts from a move plan (classified files only)."""
    counts: dict[tuple[str, str], int] = {}
    for entry in moves:
        project_id = entry.project_id or "unclassified"
        project_name = entry.project_name or "未分类"
        key = (project_id, project_name)
        counts[key] = counts.get(key, 0) + 1

    rows = [
        {"project_id": pid, "project_name": pname, "file_count": count}
        for (pid, pname), count in counts.items()
    ]
    rows.sort(key=lambda row: (-int(row["file_count"]), str(row["project_name"])))
    return rows


def classified_project_count(project_stats: list[dict[str, int | str]]) -> int:
    return sum(1 for row in project_stats if row["project_id"] != "unclassified")


def write_plan(path: Path, plan: list[MovePlanEntry], *, meta: dict | None = None) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
        "moves": [entry.to_dict() for entry in plan],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_plan(path: Path) -> tuple[list[MovePlanEntry], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    moves = [MovePlanEntry(**item) for item in data.get("moves") or []]
    meta = data.get("meta") or {}
    return moves, meta


def write_files_jsonl(path: Path, records: list[FileRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            row = record.to_dict()
            row.pop("raw_snippet", None)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
