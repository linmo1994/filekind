"""Load LLM classification prompts from classify_prompts.yaml (user-editable)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from filekind.models import AppConfig

DEFAULT_CLASSIFY_PROMPTS_NAME = "classify_prompts.yaml"
EXAMPLE_CLASSIFY_PROMPTS_NAME = "classify_prompts.example.yaml"

DEFAULT_MERGED_SYSTEM = """你是文档归档组件。根据文档片段判断其所属软件/系统项目。
项目定义：软件或软件系统名称，或项目编号对应的系统。
分类时优先依据文件名、正文中的项目名称与项目编号；例如「202432--CSP311基于···」中「202432--CSP311」是项目编号/名称前缀，应优先与 candidate_projects 中的 codes、aliases、name 匹配。
只输出一行 JSON：
{{"summary":"不超过{summary_max_chars}字","project_id":"...","project_name":"...","matched_by":"code|name|content|mixed","confidence":0.0-1.0,"reason":"不超过80字"}}
matched_by 含义：code=主要靠项目编号；name=主要靠系统名称；content=主要靠内容主题；mixed=多信号一致。
project_id 只能来自 candidate_projects；无法判断或 confidence 低于 0.6 则 unclassified。
不要输出 JSON 以外的任何内容。"""

DEFAULT_MERGED_USER = """文件名：{filename}
路径：{parent_path}

已识别信号：
- 项目编号命中：{detected_codes}
- 系统名称命中：{detected_names}

候选项目列表：
{candidate_projects_json}

以下为文档前 {page_count} 页内容：
---
{raw_snippet}
---
请输出 JSON。"""


@dataclass(frozen=True)
class ClassifyPrompts:
    merged_system: str
    merged_user: str
    source_path: Path | None = None


def default_classify_prompts() -> ClassifyPrompts:
    return ClassifyPrompts(
        merged_system=DEFAULT_MERGED_SYSTEM,
        merged_user=DEFAULT_MERGED_USER,
        source_path=None,
    )


def resolve_classify_prompts_path(config_path: Path, config: AppConfig) -> Path | None:
    setting = (config.paths.classify_prompts or DEFAULT_CLASSIFY_PROMPTS_NAME).strip()
    if not setting:
        return None

    path_setting = Path(setting).expanduser()
    candidates: list[Path] = []
    if path_setting.is_absolute():
        candidates.append(path_setting)
    else:
        base = config_path.resolve().parent
        candidates.extend(
            [
                base / path_setting,
                base / path_setting.name,
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_classify_prompts(config_path: Path, config: AppConfig) -> ClassifyPrompts:
    path = resolve_classify_prompts_path(config_path, config)
    if path is None:
        return default_classify_prompts()

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    merged = raw.get("merged") or {}
    system = (merged.get("system") or "").strip() or DEFAULT_MERGED_SYSTEM
    user = (merged.get("user") or "").strip() or DEFAULT_MERGED_USER
    return ClassifyPrompts(merged_system=system, merged_user=user, source_path=path)
