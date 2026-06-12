from __future__ import annotations

import re
from typing import Iterable

from filekind.models import FileRecord, ProjectDef

# 规格书/版型文件名：202304_CV352-BA32-11、202301_CV960X-B55-11 Specification.pdf
_FILENAME_INVENTORY_CODE = re.compile(r"(?i)^(20\d{4})[_-]")
_FILENAME_PREFIX = re.compile(
    r"(?i)\d{6}[_-]([A-Z0-9]+(?:-[A-Z0-9]+)*)"
)
_MODEL_CHAIN = re.compile(r"(?i)\b([A-Z]{2,10}\d{0,4}(?:-[A-Z0-9]+)+)\b")
_MODEL_CORE = re.compile(r"(?i)\b([A-Z]{2,10}\d{1,4})\b")
_INVENTORY_CODE = re.compile(r"(?i)\d{6}--[A-Z0-9]+")
_INVENTORY_SERIAL = re.compile(r"(?i)^20\d{4}$")
_PLATFORM_FRAGMENT = re.compile(r"(?i)([A-Z]{2,10}\d{0,4}[A-Z]?)")
_PLATFORM_DIGIT_PREFIX = re.compile(r"(?i)^([A-Z]{2,10}\d+)")

# 用于在多个同平台子项目中消歧
_REGION_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("欧规", ("欧规", "欧洲", "europe", "eu", "european")),
    ("亚太", ("亚太", "asia", "apac", "亚太区")),
    ("南美", ("南美", "south america", "latam", "拉美")),
    ("北美", ("北美", "north america", "na ")),
    ("国内", ("国内", "china", "中国区")),
]


def _normalize(s: str) -> str:
    return s.casefold()


def _add_token(found: list[str], seen: set[str], raw: str) -> None:
    value = raw.strip().upper()
    if len(value) < 2 or value in seen:
        return
    seen.add(value)
    found.append(value)


def expand_platform_prefixes(tokens: Iterable[str]) -> list[str]:
    """Derive platform family codes such as CV960 from CV960X-B55-11."""
    found: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        upper = token.strip().upper()
        if not upper:
            continue
        _add_token(found, seen, upper)

        head = re.split(r"[_\-\s./\\]+", upper)[0]
        _add_token(found, seen, head)

        digit_prefix = _PLATFORM_DIGIT_PREFIX.match(head)
        if digit_prefix:
            _add_token(found, seen, digit_prefix.group(1))

        letters = re.match(r"(?i)^([A-Z]{2,10})(?=\d)", head)
        if letters and digit_prefix:
            _add_token(found, seen, letters.group(1) + digit_prefix.group(1)[len(letters.group(1)) :])

    return found


def extract_inventory_code_from_filename(filename: str) -> str:
    match = _FILENAME_INVENTORY_CODE.match(filename.strip())
    return match.group(1).upper() if match else ""


def extract_board_type_from_filename(filename: str) -> str:
    """Extract board/model chain such as CV950D4-B42-12 from spec filenames."""
    match = _FILENAME_PREFIX.search(filename)
    if match:
        return match.group(1).upper()
    for token in extract_filename_tokens(filename):
        if "-" in token and re.search(r"[A-Z]", token):
            return token.upper()
    return ""


def board_type_matches(file_board: str, project_board: str) -> bool:
    file_board = file_board.strip().upper()
    project_board = project_board.strip().upper()
    if not file_board or not project_board:
        return False
    if file_board == project_board:
        return True
    return file_board.startswith(f"{project_board}-") or project_board.startswith(
        file_board.split("-")[0]
    )


def project_inventory_code(project: ProjectDef) -> str:
    if project.inventory_code:
        return project.inventory_code.upper()
    for code in project.codes:
        if _INVENTORY_SERIAL.fullmatch(code.strip()):
            return code.strip().upper()
    return ""


def match_project_by_inventory_metadata(
    record: FileRecord,
    projects: Iterable[ProjectDef],
) -> ProjectDef | None:
    inventory_code = extract_inventory_code_from_filename(record.filename)
    if not inventory_code:
        for code in record.detected_codes or []:
            if _INVENTORY_SERIAL.fullmatch(code.strip()):
                inventory_code = code.strip().upper()
                break
    if not inventory_code:
        return None

    matches = [
        project
        for project in projects
        if project_inventory_code(project) == inventory_code
        or inventory_code in {c.upper() for c in project.codes}
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    file_board = extract_board_type_from_filename(record.filename)
    if file_board:
        board_matches = [
            project
            for project in matches
            if project.board_type and board_type_matches(file_board, project.board_type)
        ]
        if len(board_matches) == 1:
            return board_matches[0]

    regions = _region_hints_in_text(f"{record.filename} {record.parent_path}")
    if regions:
        region_matches = [
            project for project in matches if any(region in project.name for region in regions)
        ]
        if len(region_matches) == 1:
            return region_matches[0]

    return None


def extract_filename_tokens(filename: str, parent_path: str = "") -> list[str]:
    """Pull chip/platform tokens from filename and path (spec sheets, reports)."""
    text = f"{filename} {parent_path}"
    found: list[str] = []
    seen: set[str] = set()

    for pattern in (_FILENAME_PREFIX, _MODEL_CHAIN, _MODEL_CORE, _INVENTORY_CODE):
        for match in pattern.finditer(text):
            _add_token(found, seen, match.group(1) if match.lastindex else match.group(0))

    for part in re.split(r"[_\-\s./\\]+", text):
        part = part.strip()
        if not part:
            continue
        if _MODEL_CORE.fullmatch(part) or _INVENTORY_CODE.fullmatch(part):
            _add_token(found, seen, part)

    return expand_platform_prefixes(found)


def extract_platform_prefixes(
    filename: str,
    parent_path: str = "",
    detected_codes: Iterable[str] | None = None,
) -> list[str]:
    tokens = list(detected_codes or []) + extract_filename_tokens(filename, parent_path)
    return expand_platform_prefixes(tokens)


def _project_platform_codes(project: ProjectDef) -> set[str]:
    codes: set[str] = set()
    for field in (
        project.name,
        *project.aliases,
        *project.codes,
        project.description,
        project.solution_name,
        project.board_type,
        project.inventory_code,
    ):
        if not field:
            continue
        for match in _PLATFORM_FRAGMENT.finditer(field):
            fragment = match.group(1).upper()
            if len(fragment) < 3 or fragment.isdigit():
                continue
            codes.add(fragment)
            digit_prefix = _PLATFORM_DIGIT_PREFIX.match(fragment)
            if digit_prefix:
                codes.add(digit_prefix.group(1).upper())
        for code in project.codes:
            codes.add(code.upper())
    return codes


def project_matches_platform(project: ProjectDef, prefix: str) -> bool:
    prefix = prefix.upper()
    if len(prefix) < 3:
        return False

    name_upper = project.name.upper()
    if name_upper.startswith(prefix):
        return True

    for code in _project_platform_codes(project):
        if code == prefix or code.startswith(prefix) or prefix.startswith(code):
            return True
    return False


def projects_matching_platforms(
    projects: Iterable[ProjectDef],
    prefixes: Iterable[str],
) -> list[ProjectDef]:
    prefix_list = [p.upper() for p in prefixes if len(p.strip()) >= 3]
    if not prefix_list:
        return []

    matched: list[ProjectDef] = []
    seen_ids: set[str] = set()
    for project in projects:
        if any(project_matches_platform(project, prefix) for prefix in prefix_list):
            if project.id not in seen_ids:
                seen_ids.add(project.id)
                matched.append(project)
    return matched


def _region_hints_in_text(text: str) -> list[str]:
    hay = _normalize(text)
    hits: list[str] = []
    for label, keywords in _REGION_HINTS:
        if any(kw in hay for kw in keywords):
            hits.append(label)
    return hits


def score_project_match(record: FileRecord, project: ProjectDef) -> float:
    hay = "\n".join(
        [
            record.filename,
            record.parent_path,
            record.raw_snippet[:800],
        ]
    )
    hay_norm = _normalize(hay)
    score = 0.0

    file_tokens = {
        t.upper()
        for t in (record.detected_codes or [])
        + extract_filename_tokens(record.filename, record.parent_path)
    }
    platform_prefixes = record.platform_prefixes or extract_platform_prefixes(
        record.filename,
        record.parent_path,
        record.detected_codes,
    )

    for code in project.codes:
        norm = _normalize(code)
        if norm and norm in hay_norm:
            score += 12.0
        if code.upper() in file_tokens:
            score += 10.0

    inv_code = project_inventory_code(project)
    file_inv = extract_inventory_code_from_filename(record.filename)
    if inv_code and file_inv and inv_code == file_inv:
        score += 20.0

    file_board = extract_board_type_from_filename(record.filename)
    if project.board_type and file_board and board_type_matches(file_board, project.board_type):
        score += 14.0

    if project.solution_name and project.solution_name.upper() in file_tokens:
        score += 8.0

    if project.name in (record.detected_names or []):
        score += 9.0

    name_norm = _normalize(project.name)
    name_upper = project.name.upper()
    if len(name_norm) >= 4 and name_norm in hay_norm:
        score += 7.0

    proj_tokens = _project_platform_codes(project)
    overlap = file_tokens & proj_tokens
    score += len(overlap) * 3.5

    for token in file_tokens:
        if len(token) >= 3 and _normalize(token) in name_norm:
            score += 2.5

    for prefix in platform_prefixes:
        if name_upper.startswith(prefix.upper()):
            score += 11.0
        elif prefix.upper() in proj_tokens:
            score += 9.0
        for code in proj_tokens:
            if code.startswith(prefix.upper()) or prefix.upper().startswith(code):
                score += 7.0

    regions = _region_hints_in_text(hay)
    for region in regions:
        if region in project.name:
            score += 4.0

    return score


def narrow_candidates(
    record: FileRecord,
    projects: Iterable[ProjectDef],
    *,
    limit: int = 10,
    min_score: float = 2.0,
) -> list[ProjectDef]:
    """Return top-K projects most likely to match this file."""
    project_list = list(projects)
    if not project_list:
        return []

    platform_prefixes = record.platform_prefixes or extract_platform_prefixes(
        record.filename,
        record.parent_path,
        record.detected_codes,
    )

    inventory_code = extract_inventory_code_from_filename(record.filename)
    if inventory_code:
        inventory_pool = [
            project
            for project in project_list
            if project_inventory_code(project) == inventory_code
            or inventory_code in {c.upper() for c in project.codes}
        ]
        if inventory_pool:
            search_pool = inventory_pool
        else:
            search_pool = projects_matching_platforms(project_list, platform_prefixes) or project_list
    else:
        platform_pool = projects_matching_platforms(project_list, platform_prefixes)
        search_pool = platform_pool or project_list

    scored = [
        (score_project_match(record, project), project)
        for project in search_pool
    ]
    scored = [(s, p) for s, p in scored if s >= min_score]
    scored.sort(key=lambda item: (-item[0], item[1].name))

    if not scored:
        if platform_pool:
            return platform_pool[:limit]
        if record.detected_names:
            name_set = {_normalize(n) for n in record.detected_names}
            named = [p for p in project_list if _normalize(p.name) in name_set]
            if named:
                return named[:limit]
        return []

    top_score = scored[0][0]
    cutoff = max(min_score, top_score * 0.45)
    selected = [p for s, p in scored if s >= cutoff][:limit]

    regions = _region_hints_in_text(
        f"{record.filename} {record.parent_path} {record.raw_snippet[:400]}"
    )
    if regions and len(selected) > 1:
        region_matched = [p for p in selected if any(r in p.name for r in regions)]
        if len(region_matched) == 1:
            return region_matched
        if len(region_matched) > 1:
            return region_matched[:limit]

    return selected


def narrow_candidates_with_scores(
    record: FileRecord,
    projects: Iterable[ProjectDef],
    *,
    limit: int = 10,
) -> tuple[list[ProjectDef], list[float]]:
    candidates = narrow_candidates(record, projects, limit=limit)
    scores = [score_project_match(record, p) for p in candidates]
    return candidates, scores


def unique_high_confidence_match(
    record: FileRecord,
    projects: Iterable[ProjectDef],
    *,
    min_score: float = 8.0,
    gap_ratio: float = 1.8,
) -> ProjectDef | None:
    """When one project clearly wins, classify without LLM."""
    project_list = list(projects)
    platform_prefixes = record.platform_prefixes or extract_platform_prefixes(
        record.filename,
        record.parent_path,
        record.detected_codes,
    )
    search_pool = projects_matching_platforms(project_list, platform_prefixes) or project_list

    scored = [(score_project_match(record, p), p) for p in search_pool]
    scored = [(s, p) for s, p in scored if s >= min_score]
    if not scored:
        return None
    scored.sort(key=lambda item: -item[0])

    top_score, top_project = scored[0]
    if len(scored) == 1:
        return top_project

    second_score = scored[1][0]
    if second_score <= 0 or top_score >= second_score * gap_ratio:
        return top_project
    return None
