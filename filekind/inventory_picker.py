"""Discover and interactively pick the project inventory Excel (clerk-friendly)."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Optional

from filekind.config import InventoryNotFoundError, paths_base_dir, resolve_inventory_path, state_dir
from filekind.inventory import InventoryError, load_projects_from_inventory, looks_like_inventory_workbook
from filekind.models import AppConfig

INVENTORY_DIR_NAME = "项目清单"
LAST_INVENTORY_FILE = "last_inventory.txt"

MessageFn = Callable[[str], None]

_TEMP_EXCEL = re.compile(r"(^~\$|^\.\~|^\.~)")


def is_temp_excel(path: Path) -> bool:
    name = path.name
    if name.startswith("~$") or name.startswith(".~") or name.startswith(".~"):
        return True
    return bool(_TEMP_EXCEL.match(name))


def try_count_inventory_projects(path: Path) -> int | None:
    """Return project count if path is a valid inventory workbook, else None."""
    if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return None
    if not looks_like_inventory_workbook(path):
        return None
    try:
        return len(load_projects_from_inventory(path))
    except (InventoryError, OSError):
        return None


def inventory_search_roots(config_path: Path, source: Path) -> list[Path]:
    base = paths_base_dir(config_path)
    roots: list[Path] = []
    for candidate in (
        base / INVENTORY_DIR_NAME,
        source.resolve(),
        config_path.resolve().parent,
        base,
    ):
        if candidate.is_dir() and candidate not in roots:
            roots.append(candidate)
    return roots


def discover_inventory_candidates(
    config_path: Path,
    source: Path,
    *,
    exclude: set[Path] | None = None,
) -> list[tuple[Path, int]]:
    """Find Excel files that parse as project inventories (not every .xlsx)."""
    exclude = {p.resolve() for p in (exclude or set())}
    found: dict[Path, int] = {}

    for root in inventory_search_roots(config_path, source):
        for path in sorted(root.rglob("*.xlsx")) + sorted(root.rglob("*.xlsm")):
            resolved = path.resolve()
            if resolved in exclude or is_temp_excel(resolved):
                continue
            count = try_count_inventory_projects(resolved)
            if count is None:
                continue
            found[resolved] = count

    def sort_key(item: tuple[Path, int]) -> tuple:
        path, count = item
        name = path.name.casefold()
        prefer_list = 0 if "清单" in name or "版型" in name else 1
        try:
            depth = len(path.relative_to(source.resolve()).parts)
        except ValueError:
            depth = 99
        return (prefer_list, depth, path.name.casefold())

    return sorted(found.items(), key=sort_key)


def state_dir_for(config_path: Path) -> Path:
    return state_dir(config_path)


def load_last_inventory(config_path: Path) -> Path | None:
    marker = state_dir_for(config_path) / LAST_INVENTORY_FILE
    if not marker.is_file():
        return None
    text = marker.read_text(encoding="utf-8").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_file() and try_count_inventory_projects(path.resolve()) is not None:
        return path.resolve()
    return None


def save_last_inventory(config_path: Path, inventory_path: Path) -> None:
    folder = state_dir_for(config_path)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / LAST_INVENTORY_FILE).write_text(
        str(inventory_path.resolve()),
        encoding="utf-8",
    )


def _say(on_message: MessageFn | None, message: str) -> None:
    if on_message is not None:
        on_message(message)


def _relative_display(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def pick_inventory_from_menu(
    candidates: list[tuple[Path, int]],
    *,
    config_path: Path,
    source: Path,
    on_message: MessageFn | None = None,
) -> Path:
    base = config_path.resolve().parent
    _say(on_message, "")
    _say(on_message, "找到多个可能的项目清单，请选择一个：")
    for index, (path, count) in enumerate(candidates, start=1):
        display = _relative_display(path, base)
        _say(on_message, f"  [{index}] {path.name}（{count} 个项目）  —  {display}")
    _say(on_message, "  [0] 浏览其他 Excel 文件…")

    while True:
        try:
            raw = input("\n请输入序号: ").strip()
        except EOFError as exc:
            raise InventoryNotFoundError("未选择项目清单（输入已结束）") from exc
        if raw == "0":
            picked = native_pick_inventory_file(start_dir=source)
            if picked is None:
                _say(on_message, "未选择文件，请重新输入序号。")
                continue
            count = try_count_inventory_projects(picked)
            if count is None:
                _say(on_message, f"无法识别为项目清单: {picked.name}")
                continue
            return picked
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(candidates):
                return candidates[choice - 1][0]
        _say(on_message, f"请输入 0 到 {len(candidates)} 之间的数字。")


def native_pick_inventory_file(*, start_dir: Path) -> Path | None:
    """Open OS file picker when available; return None if cancelled or unsupported."""
    start = start_dir.resolve()
    if not start.is_dir():
        start = start.parent if start.parent.is_dir() else Path.home()

    if sys.platform == "darwin":
        script = (
            'POSIX path of (choose file with prompt "请选择项目清单 Excel" '
            f'of type {{"org.openxmlformats.spreadsheetml.sheet", "public.data"}} '
            f'default location (POSIX file "{start}")'
            ")"
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        if result.returncode != 0:
            return None
        picked = result.stdout.strip()
        return Path(picked).resolve() if picked else None

    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        picked = filedialog.askopenfilename(
            title="请选择项目清单 Excel",
            initialdir=str(start),
            filetypes=[("Excel 工作簿", "*.xlsx *.xlsm"), ("所有文件", "*.*")],
        )
        root.destroy()
        return Path(picked).resolve() if picked else None
    except Exception:
        return None


def resolve_inventory_for_run(
    config_path: Path,
    config: AppConfig,
    source: Path,
    *,
    explicit: Optional[Path] = None,
    interactive: bool = True,
    on_message: MessageFn | None = None,
) -> Path:
    """Locate inventory Excel: CLI path → last used → config → auto-discover → pick."""
    if explicit is not None:
        path = explicit.expanduser().resolve()
        count = try_count_inventory_projects(path)
        if count is None:
            raise InventoryError(
                f"无法识别为项目清单 Excel: {path}\n"
                "请确认文件含有「项目编号」「项目名称」等列。"
            )
        save_last_inventory(config_path, path)
        _say(on_message, f"项目清单: {path.name}（共 {count} 个项目）")
        return path

    last = load_last_inventory(config_path)
    if last is not None:
        count = try_count_inventory_projects(last)
        if count is not None:
            _say(on_message, f"项目清单: {last.name}（共 {count} 个项目，沿用上次的清单）")
            return last

    configured = (config.paths.inventory_excel or "").strip()
    if configured:
        try:
            path = resolve_inventory_path(config_path, config, source)
            if path is not None:
                count = try_count_inventory_projects(path) or 0
                save_last_inventory(config_path, path)
                _say(on_message, f"项目清单: {path.name}（共 {count} 个项目）")
                return path
        except InventoryNotFoundError:
            pass

    candidates = discover_inventory_candidates(config_path, source)
    if len(candidates) == 1:
        path = candidates[0][0]
        count = candidates[0][1]
        save_last_inventory(config_path, path)
        _say(on_message, f"项目清单: {path.name}（共 {count} 个项目，已自动识别）")
        return path

    if len(candidates) > 1:
        if not interactive:
            names = ", ".join(p.name for p, _ in candidates[:5])
            raise InventoryNotFoundError(
                f"发现多个项目清单 Excel，请在交互模式下选择，或使用 --inventory 指定。\n"
                f"候选: {names}"
            )
        path = pick_inventory_from_menu(
            candidates,
            config_path=config_path,
            source=source,
            on_message=on_message,
        )
        count = try_count_inventory_projects(path) or 0
        save_last_inventory(config_path, path)
        _say(on_message, f"已选择项目清单: {path.name}（共 {count} 个项目）")
        return path

    if interactive:
        _say(on_message, "未在 待整理/ 或 项目清单/ 中找到可用的项目清单 Excel。")
        _say(on_message, "请在弹出的窗口中选择清单文件…")
        picked = native_pick_inventory_file(start_dir=source)
        if picked is not None:
            count = try_count_inventory_projects(picked)
            if count is not None:
                save_last_inventory(config_path, picked)
                _say(on_message, f"已选择项目清单: {picked.name}（共 {count} 个项目）")
                return picked
            raise InventoryError(
                f"无法识别为项目清单 Excel: {picked.name}\n"
                "请确认表格含有「项目编号」「项目名称」等列。"
            )

    searched = ", ".join(str(r) for r in inventory_search_roots(config_path, source))
    raise InventoryNotFoundError(
        "未找到项目清单 Excel。\n"
        f"请将清单放入「待整理/」或「{INVENTORY_DIR_NAME}/」，"
        "或在运行时通过 --inventory 指定。\n"
        f"已查找目录: {searched}"
    )
