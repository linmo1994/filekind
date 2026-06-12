"""Load LLM classification prompts from plain text or legacy YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Formatter

import yaml

from filekind.models import AppConfig

DEFAULT_CLASSIFY_PROMPTS_TXT = "classify_prompts.txt"
DEFAULT_CLASSIFY_PROMPTS_NAME = "classify_prompts.yaml"
EXAMPLE_CLASSIFY_PROMPTS_TXT = "classify_prompts.example.txt"
EXAMPLE_CLASSIFY_PROMPTS_NAME = "classify_prompts.example.yaml"

TEXT_SECTION_SYSTEM = "=== 系统说明 ==="
TEXT_SECTION_USER = "=== 用户模板 ==="

DEFAULT_MERGED_SYSTEM = """你是文档归档组件。根据文档片段判断其所属软件/系统项目。
项目定义：软件或软件系统名称，或项目编号对应的系统。

清单编号 + 版型规则（规格书最强信号）：
- 文件名如 202301_CV950D4-B42-12 Specification.pdf：前缀 202301 对应候选 inventory_code
- board_type 如 CV950D4-B42 与文件名 CV950D4-B42-12 前缀匹配（-12 为版本号）
- solution_name / platform_prefixes 用于辅助确认方案/平台
- 文件名含 202301_ 且候选有 inventory_code=202301 时必须归入，confidence≥0.85

版型/平台代号规则（规格书、测试资料极强信号）：
- 文件名如 202301_CV960X-B55-11、CV352-BA32-11 Specification.pdf
- 平台族代号：CV960X-B55-11→CV960；CV352-BA32-11→CV352（B55/BA32/末尾-11 为版型版本）
- 若 candidate 的 project_name 以 CV960/CV352 等平台代号开头，即使无 202432--CSP311 或完整中文项目名，也应归入
- Specification/规格书即使正文为空，也可仅凭文件名平台代号分类；勿轻易 unclassified

分类时优先依据文件名 platform_prefixes、detected_codes、项目名称与项目编号。
只输出一行 JSON：
{{"summary":"不超过{summary_max_chars}字","project_id":"...","project_name":"...","matched_by":"code|name|content|mixed","confidence":0.0-1.0,"reason":"不超过80字"}}
matched_by 含义：code=主要靠项目编号或平台代号；name=主要靠系统名称；content=主要靠内容主题；mixed=多信号一致。
project_id 只能来自 candidate_projects；文件名含平台代号且候选中存在同名前缀项目时不得 unclassified；确实无法关联时用 unclassified。
不要输出 JSON 以外的任何内容。"""

DEFAULT_MERGED_USER = """文件名：{filename}
路径：{parent_path}

已识别信号：
- 项目编号/机型串：{detected_codes}
- 平台族代号（优先匹配）：{platform_prefixes}
- 系统名称命中：{detected_names}

候选项目列表（已按平台代号/路径预筛选）：
{candidate_projects_json}

以下为文档前 {page_count} 页内容：
---
{raw_snippet}
---
请输出 JSON。"""


def format_classify_user(template: str, values: dict[str, str]) -> str:
    needed = {field for _, field, _, _ in Formatter().parse(template) if field}
    payload = {key: values.get(key, "无") for key in needed}
    return template.format(**payload)


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


def _prompt_search_candidates(config_path: Path, setting: str) -> list[Path]:
    path_setting = Path(setting).expanduser()
    if path_setting.is_absolute():
        return [path_setting]
    base = config_path.resolve().parent
    names = [path_setting.name, path_setting]
    if not setting.endswith(".txt"):
        names.extend(
            [
                DEFAULT_CLASSIFY_PROMPTS_TXT,
                EXAMPLE_CLASSIFY_PROMPTS_TXT,
            ]
        )
    if not setting.endswith(".yaml") and not setting.endswith(".yml"):
        names.extend([DEFAULT_CLASSIFY_PROMPTS_NAME, EXAMPLE_CLASSIFY_PROMPTS_NAME])
    candidates: list[Path] = []
    seen: set[Path] = set()
    for name in names:
        for path in (base / name, base / Path(name).name):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(path)
    return candidates


def resolve_classify_prompts_path(config_path: Path, config: AppConfig) -> Path | None:
    setting = (config.paths.classify_prompts or DEFAULT_CLASSIFY_PROMPTS_TXT).strip()
    if not setting:
        return None
    for candidate in _prompt_search_candidates(config_path, setting):
        if candidate.is_file():
            return candidate.resolve()
    return None


def parse_plain_text_prompts(text: str) -> tuple[str, str]:
    """Parse classify_prompts.txt with optional section markers."""
    body = text.strip()
    if not body:
        return "", ""

    if TEXT_SECTION_USER in body:
        before, after = body.split(TEXT_SECTION_USER, 1)
        system = before.replace(TEXT_SECTION_SYSTEM, "").strip()
        user = after.strip()
        return system, user

    if TEXT_SECTION_SYSTEM in body:
        system = body.replace(TEXT_SECTION_SYSTEM, "").strip()
        return system, ""

    return body, ""


def load_classify_prompts_from_file(path: Path) -> ClassifyPrompts:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        system, user = parse_plain_text_prompts(text)
        return ClassifyPrompts(
            merged_system=system or DEFAULT_MERGED_SYSTEM,
            merged_user=user or DEFAULT_MERGED_USER,
            source_path=path,
        )

    raw = yaml.safe_load(text) or {}
    merged = raw.get("merged") or {}
    system = (merged.get("system") or "").strip() or DEFAULT_MERGED_SYSTEM
    user = (merged.get("user") or "").strip() or DEFAULT_MERGED_USER
    return ClassifyPrompts(merged_system=system, merged_user=user, source_path=path)


def load_classify_prompts(config_path: Path, config: AppConfig) -> ClassifyPrompts:
    path = resolve_classify_prompts_path(config_path, config)
    if path is None:
        return default_classify_prompts()
    return load_classify_prompts_from_file(path)
