from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ProjectDef:
    id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class RuntimeConfig:
    load_models_sequentially: bool = True
    llm_confidence_threshold: float = 0.65
    max_files_per_run: int = 500
    summary_max_chars: int = 300
    extract_max_pages: int = 3
    text_fallback_chars: int = 3000
    excel_max_rows: int = 100
    cluster_similarity_threshold: float = 0.72
    dry_run_by_default: bool = True


@dataclass
class ModelsConfig:
    embedding: str = "BAAI/bge-small-zh-v1.5"
    llm_gguf: str = ""
    ocr: str = "mobile"


@dataclass
class TargetLayout:
    unclassified_dir: str = "_未分类"
    subdirs_by_extension: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class PathsConfig:
    """Default inbox / output folders relative to projects.yaml (or override on CLI)."""

    source: str = "待整理"
    dest: str = "已整理"
    inventory_excel: str = ""
    classify_prompts: str = "classify_prompts.yaml"


@dataclass
class AppConfig:
    hardware_profile: str = "8gb"
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    code_patterns: list[str] = field(default_factory=list)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    target_layout: TargetLayout = field(default_factory=TargetLayout)
    paths: PathsConfig = field(default_factory=PathsConfig)
    projects: list[ProjectDef] = field(default_factory=list)


@dataclass
class FileRecord:
    path: str
    filename: str
    parent_path: str
    extension: str
    size: int
    mtime: float
    md5: str | None = None
    extract_method: str | None = None
    pages_extracted: int = 0
    raw_snippet: str = ""
    summary: str = ""
    detected_codes: list[str] = field(default_factory=list)
    detected_names: list[str] = field(default_factory=list)
    project_id: str | None = None
    project_name: str | None = None
    confidence: float = 0.0
    classified_by: str | None = None
    matched_by: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class MovePlanEntry:
    source: str
    destination: str
    project_id: str
    project_name: str
    confidence: float
    classified_by: str
    matched_by: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MoveManifestEntry:
    source: str
    destination: str
    moved_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()
