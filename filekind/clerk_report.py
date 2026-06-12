"""Human-readable reports for office clerks (txt + xlsx)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from filekind.models import FileRecord
from filekind.plan.planner import summarize_projects

REPORT_TXT_NAME = "整理结果.txt"
REPORT_XLSX_NAME = "整理结果.xlsx"


def _classified_by_label(value: str) -> str:
    mapping = {
        "rule": "规则匹配",
        "vector": "内容关联",
        "llm": "AI 分类",
        "cluster": "同类归并",
        "none": "未分类",
    }
    return mapping.get(value or "", value or "—")


def write_clerk_reports(
    work_dir: Path,
    records: list[FileRecord],
    *,
    dest_root: Path,
    inventory_path: Path | None,
    inventory_project_count: int,
    also_write_beside_dest: bool = True,
) -> tuple[Path, Path | None]:
    """Write 整理结果.txt and 整理结果.xlsx under work_dir; optionally copy beside dest."""
    work_dir.mkdir(parents=True, exist_ok=True)
    stats = summarize_projects(records)
    classified = sum(
        row["file_count"] for row in stats if row["project_id"] != "unclassified"
    )
    unclassified = sum(
        row["file_count"] for row in stats if row["project_id"] == "unclassified"
    )
    project_rows = [row for row in stats if row["project_id"] != "unclassified"]
    now = datetime.now(timezone.utc).astimezone()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")

    txt_path = work_dir / REPORT_TXT_NAME
    lines = [
        "filekind 整理结果",
        f"生成时间: {stamp}",
        "",
        f"共处理 {len(records)} 个文件",
        f"已归入项目: {classified} 个",
        f"未分类: {unclassified} 个",
        f"分出项目数: {len(project_rows)}",
    ]
    if inventory_path is not None:
        lines.append(
            f"项目清单: {inventory_path.name}（共 {inventory_project_count} 个项目）"
        )
    lines.extend(["", "—— 各项目文件数 ——"])
    for row in project_rows:
        lines.append(f"  {row['project_name']}: {row['file_count']}")
    if unclassified:
        lines.append(f"  未分类: {unclassified}")

    lines.extend(["", "—— 文件明细 ——"])
    for record in records:
        status = record.project_name if record.project_id != "unclassified" else "未分类"
        reason = (record.reason or "").strip()
        line = f"{record.filename}  →  {status}"
        if record.confidence > 0:
            line += f"  （{record.confidence:.0%}）"
        if reason and record.project_id == "unclassified":
            line += f"  [{reason}]"
        lines.append(line)

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    xlsx_path: Path | None = None
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "整理结果"
        headers = ["文件名", "归入项目", "分类方式", "置信度", "说明"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for record in records:
            ws.append(
                [
                    record.filename,
                    record.project_name or "未分类",
                    _classified_by_label(record.classified_by),
                    round(record.confidence, 2) if record.confidence else "",
                    (record.reason or "").strip(),
                ]
            )
        xlsx_path = work_dir / REPORT_XLSX_NAME
        wb.save(xlsx_path)
    except Exception:
        xlsx_path = None

    if also_write_beside_dest:
        dest_parent = dest_root.resolve().parent
        dest_parent.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%Y%m%d-%H%M")
        copy_txt = dest_parent / f"整理结果-{ts}.txt"
        copy_txt.write_text(txt_path.read_text(encoding="utf-8"), encoding="utf-8")
        if xlsx_path is not None and xlsx_path.is_file():
            copy_xlsx = dest_parent / f"整理结果-{ts}.xlsx"
            copy_xlsx.write_bytes(xlsx_path.read_bytes())

    return txt_path, xlsx_path
