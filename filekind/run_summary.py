"""Final run summary for clerks (console + optional report lines)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

EchoFn = Callable[[str], None]


def _inventory_projects(meta: dict[str, Any]) -> list[dict[str, str]]:
    rows = meta.get("inventory_projects") or []
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        name = str(row.get("name") or pid).strip()
        if pid or name:
            out.append({"id": pid or name, "name": name or pid})
    return out


def _project_stats(meta: dict[str, Any]) -> list[dict[str, Any]]:
    return list(meta.get("project_stats") or [])


def compute_run_summary(meta: dict[str, Any]) -> dict[str, Any]:
    stats = _project_stats(meta)
    total_files = int(meta.get("file_count") or 0)
    classified_files = sum(
        int(row.get("file_count") or 0)
        for row in stats
        if row.get("project_id") != "unclassified"
    )
    unclassified_files = sum(
        int(row.get("file_count") or 0)
        for row in stats
        if row.get("project_id") == "unclassified"
    )
    if not total_files:
        total_files = classified_files + unclassified_files

    matched_project_ids = {
        str(row.get("project_id") or "")
        for row in stats
        if row.get("project_id") not in (None, "", "unclassified")
        and int(row.get("file_count") or 0) > 0
    }
    classified_project_count = len(matched_project_ids)

    inventory = _inventory_projects(meta)
    inventory_count = int(meta.get("inventory_project_count") or 0)
    if not inventory_count and inventory:
        inventory_count = len(inventory)

    unmatched: list[str] = []
    if inventory:
        unmatched = [
            p["name"]
            for p in inventory
            if p["id"] not in matched_project_ids
        ]

    project_rows = [
        row for row in stats if row.get("project_id") != "unclassified"
    ]

    return {
        "inventory_count": inventory_count,
        "classified_project_count": classified_project_count,
        "total_files": total_files,
        "classified_files": classified_files,
        "unclassified_files": unclassified_files,
        "unmatched_projects": unmatched,
        "project_rows": project_rows,
    }


def format_run_summary_lines(
    meta: dict[str, Any],
    *,
    title: str = "整理汇总",
) -> list[str]:
    if not _project_stats(meta) and not int(meta.get("file_count") or 0):
        return []

    s = compute_run_summary(meta)
    lines = [
        "",
        "=" * 72,
        title,
        "=" * 72,
    ]

    if s["inventory_count"]:
        lines.append(f"项目清单中共有 {s['inventory_count']} 个项目。")
    lines.append(
        f"本次已识别并归类到 {s['classified_project_count']} 个项目，"
        f"共处理 {s['total_files']} 个文件，"
        f"其中 {s['classified_files']} 个已归入项目。"
    )
    if s["unclassified_files"]:
        lines.append(f"另有 {s['unclassified_files']} 个文件未能归入任何项目（未分类）。")

    unmatched = s["unmatched_projects"]
    if unmatched:
        lines.append("")
        lines.append(f"清单中未被识别出资料的项目共 {len(unmatched)} 个：")
        for name in unmatched:
            lines.append(f"  · {name}")
    elif s["inventory_count"]:
        lines.append("")
        lines.append("清单中的项目在本次待整理资料中均有对应文件。")

    project_rows = s["project_rows"]
    if project_rows:
        lines.append("")
        lines.append("各项目文件数：")
        for row in project_rows:
            lines.append(f"  · {row['project_name']}: {row['file_count']}")
    if s["unclassified_files"]:
        lines.append(f"  · 未分类: {s['unclassified_files']}")

    lines.append("=" * 72)
    return lines


def print_run_summary(
    meta: dict[str, Any],
    *,
    echo: EchoFn,
    title: str = "整理汇总",
) -> None:
    for line in format_run_summary_lines(meta, title=title):
        echo(line)


def inventory_projects_payload(projects: list[Any]) -> list[dict[str, str]]:
    return [{"id": p.id, "name": p.name} for p in projects]
