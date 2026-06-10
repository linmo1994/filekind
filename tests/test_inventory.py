from pathlib import Path

import pytest
from openpyxl import Workbook

from filekind.config import resolve_inventory_path
from filekind.inventory import InventoryError, load_projects_from_inventory
from filekind.models import AppConfig, PathsConfig
from filekind.scan.scanner import scan_directory


def _write_inventory(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["项目编号", "项目名称"])
    ws.append(["202432--CSP311", "基于Android T高级智能会议平板系统"])
    ws.append(["202414--CV6683", "基于Android R南美智能数字电视系统"])
    wb.save(path)


def test_load_projects_from_inventory(tmp_path: Path) -> None:
    xlsx = tmp_path / "国高资料清单2026 版型清单.xlsx"
    _write_inventory(xlsx)
    projects = load_projects_from_inventory(xlsx)
    assert len(projects) == 2
    assert projects[0].codes == ["202432--CSP311"]
    assert "会议平板" in projects[0].name


def test_resolve_inventory_in_source_dir(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.write_text("paths:\n  inventory_excel: list.xlsx\n", encoding="utf-8")
    source = tmp_path / "待整理"
    source.mkdir()
    inv = source / "list.xlsx"
    _write_inventory(inv)
    config = AppConfig(paths=PathsConfig(inventory_excel="list.xlsx"))
    resolved = resolve_inventory_path(config_path, config, source)
    assert resolved == inv.resolve()


def test_resolve_inventory_recursive_in_source(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    source = tmp_path / "待整理"
    nested = source / "2026" / "清单"
    nested.mkdir(parents=True)
    inv = nested / "国高资料清单2026 版型清单.xlsx"
    _write_inventory(inv)
    config = AppConfig(paths=PathsConfig(inventory_excel="国高资料清单2026 版型清单.xlsx"))
    resolved = resolve_inventory_path(config_path, config, source)
    assert resolved == inv.resolve()


def test_resolve_inventory_prefers_shallowest_match(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    source = tmp_path / "待整理"
    shallow = source / "list.xlsx"
    deep = source / "a" / "b" / "list.xlsx"
    deep.parent.mkdir(parents=True)
    _write_inventory(shallow)
    _write_inventory(deep)
    config = AppConfig(paths=PathsConfig(inventory_excel="list.xlsx"))
    resolved = resolve_inventory_path(config_path, config, source)
    assert resolved == shallow.resolve()


def test_scan_excludes_inventory_only_when_filtered_in_pipeline(tmp_path: Path) -> None:
    inbox = tmp_path / "in"
    inbox.mkdir()
    inv = inbox / "list.xlsx"
    _write_inventory(inv)
    (inbox / "202432--CSP311测试报告.pdf").write_bytes(b"pdf")

    all_records = scan_directory(inbox, max_files=100)
    assert len(all_records) == 2

    projects = load_projects_from_inventory(inv)
    inv_resolved = inv.resolve()
    filtered = [r for r in all_records if Path(r.path).resolve() != inv_resolved]
    assert len(filtered) == 1
    assert filtered[0].filename.endswith(".pdf")


def test_inventory_missing_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.touch()
    config = AppConfig(paths=PathsConfig(inventory_excel="missing.xlsx"))
    source = tmp_path / "in"
    source.mkdir()
    with pytest.raises(Exception, match="未找到项目清单"):
        resolve_inventory_path(config_path, config, source)


def test_empty_inventory_workbook_raises(tmp_path: Path) -> None:
    xlsx = tmp_path / "empty.xlsx"
    Workbook().save(xlsx)
    with pytest.raises(InventoryError, match="未解析到任何项目"):
        load_projects_from_inventory(xlsx)
