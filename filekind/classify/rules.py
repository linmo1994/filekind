from __future__ import annotations

import re
from typing import Iterable

from filekind.config import compile_code_patterns
from filekind.models import AppConfig, FileRecord, ProjectDef


def _normalize(s: str) -> str:
    return s.casefold()


def detect_codes(text: str, patterns: list[re.Pattern[str]]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(0).upper()
            if value not in seen:
                seen.add(value)
                found.append(value)
    return found


def _project_code_index(projects: Iterable[ProjectDef]) -> dict[str, ProjectDef]:
    index: dict[str, ProjectDef] = {}
    for project in projects:
        for code in project.codes:
            index[_normalize(code)] = project
    return index


def _project_name_terms(projects: Iterable[ProjectDef]) -> list[tuple[str, ProjectDef]]:
    terms: list[tuple[str, ProjectDef]] = []
    for project in projects:
        for term in [project.name, *project.aliases]:
            term = term.strip()
            if len(term) >= 2:
                terms.append((_normalize(term), project))
    terms.sort(key=lambda x: len(x[0]), reverse=True)
    return terms


def collect_signals(record: FileRecord, config: AppConfig) -> FileRecord:
    patterns = compile_code_patterns(config.code_patterns)
    haystack = "\n".join(
        [
            record.filename,
            record.parent_path,
            record.raw_snippet,
        ]
    )
    record.detected_codes = detect_codes(haystack, patterns)

    hay_norm = _normalize(haystack)
    for project in config.projects:
        for code in project.codes:
            if _normalize(code) in hay_norm or code.upper() in haystack.upper():
                if code.upper() not in {c.upper() for c in record.detected_codes}:
                    record.detected_codes.append(code.upper())

    name_terms = _project_name_terms(config.projects)
    names: list[str] = []
    for term, project in name_terms:
        if term in hay_norm:
            names.append(project.name)
    record.detected_names = list(dict.fromkeys(names))
    return record


def apply_rules(record: FileRecord, config: AppConfig) -> FileRecord:
    if record.project_id:
        return record

    code_index = _project_code_index(config.projects)
    for code in record.detected_codes:
        project = code_index.get(_normalize(code))
        if project:
            record.project_id = project.id
            record.project_name = project.name
            record.confidence = 0.95
            record.classified_by = "rule"
            record.matched_by = "code"
            record.reason = f"命中项目编号 {code}"
            return record

    if record.detected_names:
        name_map = {_normalize(p.name): p for p in config.projects}
        for alias_hit in record.detected_names:
            project = name_map.get(_normalize(alias_hit))
            if project:
                record.project_id = project.id
                record.project_name = project.name
                record.confidence = 0.88
                record.classified_by = "rule"
                record.matched_by = "name"
                record.reason = f"命中系统名称 {alias_hit}"
                return record

    return record


def is_classified(record: FileRecord, threshold: float) -> bool:
    return bool(
        record.project_id
        and record.project_id != "unclassified"
        and record.confidence >= threshold
    )
