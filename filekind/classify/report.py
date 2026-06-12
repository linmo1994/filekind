from __future__ import annotations

from filekind.classify.rules import is_classified
from filekind.models import FileRecord
from filekind.plan.planner import summarize_projects


def classified_count(records: list[FileRecord], threshold: float) -> int:
    return sum(1 for record in records if is_classified(record, threshold))


def project_stats_for_classified(
    records: list[FileRecord],
    threshold: float,
) -> list[dict[str, int | str]]:
    classified = [r for r in records if is_classified(r, threshold)]
    return summarize_projects(classified)


def format_llm_result_line(record: FileRecord, threshold: float) -> str:
    if is_classified(record, threshold):
        return (
            f"{record.filename} → {record.project_name}"
            f"（置信度 {record.confidence:.2f}）"
        )
    reason = (record.reason or "未分类").strip()
    return f"{record.filename} → 未分类（{reason}）"


def emit_stage_summary(
    say,
    title: str,
    records: list[FileRecord],
    threshold: float,
    *,
    previous_classified: int = 0,
    max_projects: int = 20,
) -> int:
    """Print staged classification stats; return current classified count."""
    total = len(records)
    classified_total = classified_count(records, threshold)
    newly = max(0, classified_total - previous_classified)
    unresolved = total - classified_total
    stats = project_stats_for_classified(records, threshold)
    project_count = len(stats)

    say("")
    say(f"【{title}】")
    if newly:
        say(
            f"  本阶段新增: {newly} 个；"
            f"累计已分类 {classified_total}/{total} 个 → {project_count} 个项目，"
            f"待分类 {unresolved} 个"
        )
    else:
        say(
            f"  累计已分类 {classified_total}/{total} 个 → {project_count} 个项目，"
            f"待分类 {unresolved} 个"
        )

    if stats:
        say("  各项目文件数:")
        for row in stats[:max_projects]:
            say(f"    - {row['project_name']}: {row['file_count']}")
        if len(stats) > max_projects:
            say(f"    … 另有 {len(stats) - max_projects} 个项目")

    return classified_total
