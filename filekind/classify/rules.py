from __future__ import annotations

import re
from typing import Iterable

from filekind.classify.candidates import (
    extract_filename_tokens,
    extract_inventory_code_from_filename,
    extract_platform_prefixes,
    match_project_by_inventory_metadata,
    narrow_candidates,
    project_inventory_code,
    score_project_match,
    unique_high_confidence_match,
)
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
        inv = project_inventory_code(project)
        if inv:
            index[_normalize(inv)] = project
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
    seen_codes = {c.upper() for c in record.detected_codes}
    for token in extract_filename_tokens(record.filename, record.parent_path):
        upper = token.upper()
        if upper not in seen_codes:
            seen_codes.add(upper)
            record.detected_codes.append(upper)

    inventory_code = extract_inventory_code_from_filename(record.filename)
    if inventory_code and inventory_code not in seen_codes:
        seen_codes.add(inventory_code)
        record.detected_codes.append(inventory_code)

    hay_norm = _normalize(haystack)
    for project in config.projects:
        inv = project_inventory_code(project)
        if inv and (_normalize(inv) in hay_norm or inv in record.filename.upper()):
            if inv not in seen_codes:
                seen_codes.add(inv)
                record.detected_codes.append(inv)
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
    record.platform_prefixes = extract_platform_prefixes(
        record.filename,
        record.parent_path,
        record.detected_codes,
    )
    return record


def apply_rules(record: FileRecord, config: AppConfig) -> FileRecord:
    if record.project_id:
        return record

    inventory_match = match_project_by_inventory_metadata(record, config.projects)
    if inventory_match is not None:
        record.project_id = inventory_match.id
        record.project_name = inventory_match.name
        record.confidence = 0.93
        record.classified_by = "rule"
        record.matched_by = "code"
        inv = project_inventory_code(inventory_match) or inventory_match.inventory_code
        record.reason = f"命中清单编号 {inv}"
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


def apply_narrow_rule(record: FileRecord, config: AppConfig) -> FileRecord:
    """Classify when filename/path tokens uniquely identify one project."""
    if record.project_id:
        return record

    project = unique_high_confidence_match(record, config.projects)
    if project is None:
        narrowed = narrow_candidates(
            record,
            config.projects,
            limit=config.runtime.llm_max_candidates,
        )
        if len(narrowed) == 1:
            score = score_project_match(record, narrowed[0])
            if score >= 6.0:
                project = narrowed[0]

    if project is None:
        return record

    record.project_id = project.id
    record.project_name = project.name
    record.confidence = 0.82
    record.classified_by = "rule"
    record.matched_by = "code"
    record.reason = "代号/路径唯一匹配"
    return record


def is_classified(record: FileRecord, threshold: float) -> bool:
    return bool(
        record.project_id
        and record.project_id != "unclassified"
        and record.confidence >= threshold
    )
