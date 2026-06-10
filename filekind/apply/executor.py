from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from filekind.models import MoveManifestEntry, MovePlanEntry, resolve_path
from filekind.path_utils import same_file_content, unique_on_disk


class ApplyError(Exception):
    pass


@dataclass
class ApplyResult:
    copied: list[MoveManifestEntry] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def moved(self) -> list[MoveManifestEntry]:
        """Backward-compatible alias."""
        return self.copied


def apply_plan(
    plan: list[MovePlanEntry],
    *,
    manifest_path: Path,
    dry_run: bool = False,
) -> ApplyResult:
    result = ApplyResult()
    moved_at = datetime.now(timezone.utc).isoformat()

    for entry in plan:
        src = resolve_path(entry.source)
        dest = resolve_path(entry.destination)

        if not src.exists():
            result.skipped.append(f"源文件不存在，已跳过: {src.name}")
            continue

        if src.resolve() == dest.resolve():
            result.skipped.append(f"源与目标相同，已跳过: {src.name}")
            continue

        if dest.exists():
            if same_file_content(src, dest):
                result.skipped.append(f"目标位置已有相同文件，已跳过: {dest.name}")
                continue
            dest = unique_on_disk(dest)

        if dry_run:
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
        result.copied.append(
            MoveManifestEntry(source=str(src), destination=str(dest), moved_at=moved_at)
        )

    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "created_at": moved_at,
                    "mode": "copy",
                    "entries": [m.to_dict() for m in result.copied],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return result


def rollback(manifest_path: Path, *, dry_run: bool = False) -> int:
    """Remove copied files under 已整理; originals in 待整理 are left unchanged."""
    data = json.loads(resolve_path(manifest_path).read_text(encoding="utf-8"))
    entries = data.get("entries") or []
    count = 0
    for item in reversed(entries):
        copy_path = Path(item["destination"])
        if not copy_path.exists():
            continue
        if dry_run:
            count += 1
            continue
        copy_path.unlink()
        count += 1
    return count
