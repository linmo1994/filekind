from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import yaml

from filekind.models import (
    AppConfig,
    ModelsConfig,
    PathsConfig,
    ProjectDef,
    RuntimeConfig,
    TargetLayout,
    resolve_path,
)

DEFAULT_CONFIG_NAME = "projects.yaml"
EXAMPLE_CONFIG_NAME = "projects.example.yaml"


def _runtime_from_dict(data: dict | None) -> RuntimeConfig:
    data = data or {}
    known = RuntimeConfig.__dataclass_fields__
    return RuntimeConfig(**{k: data[k] for k in data if k in known})


def _models_from_dict(data: dict | None) -> ModelsConfig:
    data = data or {}
    known = ModelsConfig.__dataclass_fields__
    return ModelsConfig(**{k: data[k] for k in data if k in known})


def _layout_from_dict(data: dict | None) -> TargetLayout:
    data = data or {}
    return TargetLayout(
        unclassified_dir=data.get("unclassified_dir", "_未分类"),
        subdirs_by_extension=data.get("subdirs_by_extension", {}),
    )


def _paths_from_dict(data: dict | None) -> PathsConfig:
    data = data or {}
    known = PathsConfig.__dataclass_fields__
    return PathsConfig(**{k: data[k] for k in data if k in known})


def resolve_path_setting(value: str, *, base_dir: Path) -> Path:
    """Expand ~; resolve relative paths against the config file directory."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


class RunPathsError(ValueError):
    pass


def resolve_run_paths(
    config_path: Path,
    config: AppConfig,
    source: Optional[Path] = None,
    dest: Optional[Path] = None,
    *,
    create_dest: bool = True,
    create_relative_source: bool = True,
) -> tuple[Path, Path]:
    base_dir = config_path.resolve().parent
    src = (
        resolve_path(source)
        if source is not None
        else resolve_path_setting(config.paths.source, base_dir=base_dir)
    )
    dst = (
        resolve_path(dest)
        if dest is not None
        else resolve_path_setting(config.paths.dest, base_dir=base_dir)
    )

    if not src.is_dir():
        if create_relative_source and _is_relative_to_base(src, base_dir):
            src.mkdir(parents=True, exist_ok=True)
        else:
            raise RunPathsError(
                f"待整理目录不存在: {src}\n"
                f"请创建该目录，或在 projects.yaml 的 paths.source 中修改默认路径。"
            )
    if create_dest:
        dst.mkdir(parents=True, exist_ok=True)
    return src, dst


class InventoryNotFoundError(RunPathsError):
    pass


def _is_inventory_filename_only(setting: Path) -> bool:
    """True when config is a bare filename (no directory component)."""
    text = str(setting).strip()
    return bool(text) and setting.name == text and not setting.is_absolute()


def _find_inventory_under_source(source: Path, filename: str) -> Path | None:
    """Recursively find a file by name under the inbox directory."""
    root = source.resolve()
    matches = [
        path.resolve()
        for path in root.rglob(filename)
        if path.is_file() and path.name == filename
    ]
    if not matches:
        return None
    return min(matches, key=lambda path: (len(path.relative_to(root).parts), str(path)))


def resolve_inventory_path(
    config_path: Path,
    config: AppConfig,
    source: Path,
    explicit: Optional[Path] = None,
) -> Path | None:
    """Locate the project inventory Excel (relative to source or config dir)."""
    setting = explicit
    if setting is None:
        text = (config.paths.inventory_excel or "").strip()
        if not text:
            return None
        setting = Path(text)

    candidates: list[Path] = []
    if setting.is_absolute():
        candidates.append(setting)
    else:
        candidates.extend(
            [
                source / setting,
                source / setting.name,
                config_path.parent / setting,
                config_path.parent / setting.name,
                Path.cwd() / setting,
            ]
        )

    for candidate in candidates:
        path = candidate.expanduser()
        if path.is_file():
            return path.resolve()

    if _is_inventory_filename_only(setting):
        nested = _find_inventory_under_source(source, setting.name)
        if nested is not None:
            return nested

    searched = ", ".join(str(c.expanduser().resolve()) for c in candidates[:4])
    extra = ""
    if _is_inventory_filename_only(setting):
        extra = (
            f"\n已在待整理目录下递归查找文件名: {setting.name}"
            f"（待整理: {source.resolve()}）"
        )
    raise InventoryNotFoundError(
        f"未找到项目清单 Excel: {setting}\n"
        f"待整理目录: {source.resolve()}\n"
        f"请将清单放入上述待整理目录（含子目录），或在 projects.yaml 的 paths.inventory_excel 中填写正确文件名。\n"
        f"提示: 仅存在 Excel 打开时的临时文件（.~ 或 ~$ 开头）不算有效清单。\n"
        f"已查找: {searched}{extra}"
    )


def _is_relative_to_base(path: Path, base_dir: Path) -> bool:
    try:
        path.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


def is_frozen_bundle() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path | None:
    """Directory containing the packaged executable (PyInstaller)."""
    if not is_frozen_bundle():
        return None
    return Path(sys.executable).resolve().parent


def default_config_search_paths() -> list[Path]:
    root = bundle_root()
    if root is not None:
        # Packaged binary: prefer config beside the executable over cwd.
        return [root / DEFAULT_CONFIG_NAME, Path.cwd() / DEFAULT_CONFIG_NAME]
    return [Path.cwd() / DEFAULT_CONFIG_NAME]


def resolve_config_path(explicit: Optional[Path] = None) -> Path:
    """Locate projects.yaml without requiring -p on the command line."""
    if explicit is not None:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
        raise ConfigNotFoundError(path, [path.resolve()])

    for candidate in default_config_search_paths():
        if candidate.is_file():
            return candidate.resolve()

    raise ConfigNotFoundError(None, [p.resolve() for p in default_config_search_paths()])


class ConfigNotFoundError(FileNotFoundError):
    def __init__(self, requested: Path | None, searched: list[Path]):
        self.requested = requested
        self.searched = searched
        if requested is not None:
            msg = f"配置文件不存在: {requested}"
        else:
            msg = "未找到默认配置文件 projects.yaml"
        super().__init__(msg)


def config_not_found_hint(exc: ConfigNotFoundError) -> str:
    lines = [str(exc), "", "已查找:"]
    for path in exc.searched:
        lines.append(f"  - {path}")

    example_sources: list[Path] = [
        Path.cwd() / EXAMPLE_CONFIG_NAME,
    ]
    root = bundle_root()
    if root is not None:
        example_sources.append(root / EXAMPLE_CONFIG_NAME)

    for example in example_sources:
        if example.is_file():
            target = (exc.searched[0] if exc.searched else Path.cwd() / DEFAULT_CONFIG_NAME)
            lines.extend(
                [
                    "",
                    "首次使用请复制配置模板:",
                    f"  cp {example} {target.parent / DEFAULT_CONFIG_NAME}",
                    "  # 编辑 projects.yaml 后重新运行（无需 -p 参数）",
                ]
            )
            break
    else:
        lines.extend(["", "请创建 projects.yaml，或使用 -p 指定配置文件路径。"])
    return "\n".join(lines)


def load_config(path: Path | None = None, *, explicit: Optional[Path] = None) -> AppConfig:
    config_path = resolve_config_path(explicit if path is None else path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    projects = [
        ProjectDef(
            id=p["id"],
            name=p["name"],
            aliases=p.get("aliases") or [],
            codes=p.get("codes") or [],
            description=(p.get("description") or "").strip(),
        )
        for p in raw.get("projects") or []
    ]
    return AppConfig(
        hardware_profile=raw.get("hardware_profile", "8gb"),
        runtime=_runtime_from_dict(raw.get("runtime")),
        code_patterns=list(raw.get("code_patterns") or []),
        models=_models_from_dict(raw.get("models")),
        target_layout=_layout_from_dict(raw.get("target_layout")),
        paths=_paths_from_dict(raw.get("paths")),
        projects=projects,
    )


def compile_code_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p) for p in patterns]
