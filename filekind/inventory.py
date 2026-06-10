from __future__ import annotations

import re
from pathlib import Path

from openpyxl import load_workbook

from filekind.models import ProjectDef

PROJECT_CODE_IN_TEXT = re.compile(r"(?i)\d{6}--[A-Z0-9]+")

CODE_HEADERS = ("项目编号", "编号", "项目代号", "代号", "项目代码", "code")
NAME_HEADERS = ("项目名称", "系统名称", "产品名称", "名称", "系统", "name", "title")


class InventoryError(ValueError):
    pass


def _normalize_header(value: object) -> str:
    return str(value or "").strip().casefold()


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _slug_id(code: str, name: str, index: int) -> str:
    base = code or name or f"project-{index}"
    slug = re.sub(r"[^\w\-]+", "-", base.casefold()).strip("-")
    return slug[:80] or f"project-{index}"


def _extract_code(text: str) -> str:
    match = PROJECT_CODE_IN_TEXT.search(text)
    return match.group(0).upper() if match else ""


def _find_header_map(row_values: list[str]) -> dict[str, int] | None:
    normalized = [_normalize_header(v) for v in row_values]
    code_idx = None
    name_idx = None
    for idx, header in enumerate(normalized):
        if not header:
            continue
        if code_idx is None and any(
            header == alias.casefold() or header.endswith(alias.casefold()) for alias in CODE_HEADERS
        ):
            code_idx = idx
        if name_idx is None and any(
            header == alias.casefold() or header.endswith(alias.casefold()) for alias in NAME_HEADERS
        ):
            name_idx = idx
    if code_idx is None and name_idx is None:
        return None
    mapping: dict[str, int] = {}
    if code_idx is not None:
        mapping["code"] = code_idx
    if name_idx is not None:
        mapping["name"] = name_idx
    return mapping


def _projects_from_sheet_rows(rows: list[tuple[object, ...]]) -> list[ProjectDef]:
    if not rows:
        return []

    header_map = _find_header_map([_cell_text(c) for c in rows[0]])
    data_rows = rows[1:] if header_map else rows

    projects: list[ProjectDef] = []
    seen: set[str] = set()

    for row in data_rows:
        cells = [_cell_text(c) for c in row if _cell_text(c)]
        if not cells:
            continue

        code = ""
        name = ""
        if header_map:
            if "code" in header_map and header_map["code"] < len(row):
                code = _extract_code(_cell_text(row[header_map["code"]])) or _cell_text(
                    row[header_map["code"]]
                )
            if "name" in header_map and header_map["name"] < len(row):
                name = _cell_text(row[header_map["name"]])

        row_text = " ".join(cells)
        if not code:
            code = _extract_code(row_text)
        if not name:
            name = max(cells, key=len)

        if not code and not name:
            continue

        if not code and name:
            code = _extract_code(name)

        key = (code or name).casefold()
        if key in seen:
            continue
        seen.add(key)

        aliases: list[str] = []
        if code and name and code.casefold() not in name.casefold():
            aliases.append(code)
        if name and code and name != code:
            aliases.append(name)

        projects.append(
            ProjectDef(
                id=_slug_id(code, name, len(projects) + 1),
                name=name or code,
                aliases=list(dict.fromkeys(aliases)),
                codes=[code] if code else [],
                description=row_text[:500],
            )
        )

    return projects


def load_projects_from_inventory(path: Path) -> list[ProjectDef]:
    """Parse project list from an Excel inventory workbook."""
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise InventoryError(f"无法读取项目清单 Excel: {path.name} ({exc})") from exc

    projects: list[ProjectDef] = []
    seen_ids: set[str] = set()
    try:
        for sheet in wb.worksheets:
            rows: list[tuple[object, ...]] = []
            for row in sheet.iter_rows(values_only=True):
                if any(cell is not None and str(cell).strip() for cell in row):
                    rows.append(row)
                if len(rows) >= 2000:
                    break
            for project in _projects_from_sheet_rows(rows):
                if project.id in seen_ids:
                    project.id = f"{project.id}-{len(seen_ids)}"
                seen_ids.add(project.id)
                projects.append(project)
    finally:
        wb.close()

    if not projects:
        raise InventoryError(
            f"项目清单 Excel 中未解析到任何项目: {path.name}\n"
            "请确认表格含有「项目编号/项目名称」等列，或每行包含如 202432--CSP311 的项目代号。"
        )
    return projects
