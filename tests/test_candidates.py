from filekind.classify.candidates import (
    extract_filename_tokens,
    narrow_candidates,
    score_project_match,
    unique_high_confidence_match,
)
from filekind.classify.llm import _parse_json
from filekind.classify.rules import apply_narrow_rule, collect_signals
from filekind.models import AppConfig, FileRecord, ProjectDef, RuntimeConfig


def _cv352_projects() -> list[ProjectDef]:
    return [
        ProjectDef(id="cv352-eu", name="CV352基于Android P的欧规全制式智能数字电视系统软件"),
        ProjectDef(id="cv352-ap", name="CV352基于Android P的亚太智能数字电视系统软件"),
        ProjectDef(id="cv352-sa", name="CV352基于Android P的南美智能数字电视系统软件"),
    ]


def test_extract_filename_tokens_from_spec_pdf() -> None:
    tokens = extract_filename_tokens(
        "202304_CV352-BA32-11 Specification.pdf",
        "转化/规格书",
    )
    assert "CV352-BA32-11" in tokens
    assert "CV352" in tokens


def test_extract_platform_prefix_from_cv960x() -> None:
    from filekind.classify.candidates import extract_platform_prefixes

    prefixes = extract_platform_prefixes(
        "202301_CV960X-B55-11 Specification.pdf",
        "转化/规格书",
    )
    assert "CV960" in prefixes
    assert "CV960X" in prefixes


def test_cv960x_scores_against_cv960_projects() -> None:
    projects = [
        ProjectDef(id="cv960-eu", name="CV960基于Android P的欧规全制式智能数字电视系统软件"),
        ProjectDef(id="other", name="CSP311基于某平台系统软件"),
    ]
    record = FileRecord(
        path="x/spec.pdf",
        filename="202301_CV960X-B55-11 Specification.pdf",
        parent_path="转化",
        extension=".pdf",
        size=1,
        mtime=0.0,
        platform_prefixes=["CV960", "CV960X", "CV960X-B55-11"],
    )
    assert score_project_match(record, projects[0]) >= 8.0
    assert score_project_match(record, projects[1]) == 0.0


def test_narrow_candidates_includes_cv960_when_inventory_is_large() -> None:
    projects = [ProjectDef(id=f"p{i}", name=f"项目{i}系统软件") for i in range(80)]
    projects.append(
        ProjectDef(id="cv960-eu", name="CV960基于Android P的欧规全制式智能数字电视系统软件")
    )
    record = FileRecord(
        path="x/spec.pdf",
        filename="202301_CV960X-B55-11 Specification.pdf",
        parent_path="转化",
        extension=".pdf",
        size=1,
        mtime=0.0,
        platform_prefixes=["CV960", "CV960X"],
    )
    candidates = narrow_candidates(record, projects, limit=10)
    assert any(p.id == "cv960-eu" for p in candidates)
    assert "p0" not in [p.id for p in candidates]


def test_narrow_candidates_filters_by_chip_code() -> None:
    record = FileRecord(
        path="x/202304_CV352-BA32-11 Specification.pdf",
        filename="202304_CV352-BA32-11 Specification.pdf",
        parent_path="转化",
        extension=".pdf",
        size=1,
        mtime=0.0,
        detected_codes=["CV352", "CV352-BA32-11"],
    )
    candidates = narrow_candidates(record, _cv352_projects(), limit=10)
    assert len(candidates) == 3
    assert all("CV352" in p.name for p in candidates)


def test_narrow_candidates_region_disambiguation() -> None:
    record = FileRecord(
        path="x/spec.pdf",
        filename="202304_CV352-BA32-11 欧规 Specification.pdf",
        parent_path="转化/欧规",
        extension=".pdf",
        size=1,
        mtime=0.0,
        detected_codes=["CV352"],
    )
    candidates = narrow_candidates(record, _cv352_projects(), limit=10)
    assert len(candidates) == 1
    assert "欧规" in candidates[0].name


def test_unique_high_confidence_match_single_project() -> None:
    projects = [
        ProjectDef(id="csp", name="CSP311智能系统", codes=["202432--CSP311"]),
    ]
    record = FileRecord(
        path="x/202432--CSP311测试报告.pdf",
        filename="202432--CSP311测试报告.pdf",
        parent_path="转化",
        extension=".pdf",
        size=1,
        mtime=0.0,
        detected_codes=["202432--CSP311"],
    )
    assert unique_high_confidence_match(record, projects) is projects[0]


def test_apply_narrow_rule_classifies_unique_token_match(tmp_path) -> None:
    config = AppConfig(
        projects=_cv352_projects(),
        runtime=RuntimeConfig(),
    )
    record = FileRecord(
        path=str(tmp_path / "spec.pdf"),
        filename="202304_CV352-BA32-11 欧规 Specification.pdf",
        parent_path=str(tmp_path),
        extension=".pdf",
        size=1,
        mtime=0.0,
    )
    collect_signals(record, config)
    apply_narrow_rule(record, config)
    assert record.project_id == "cv352-eu"
    assert record.classified_by == "rule"


def test_score_project_match_inventory_code() -> None:
    project = ProjectDef(id="x", name="某系统", codes=["202432--CSP311"])
    record = FileRecord(
        path="a.pdf",
        filename="202432--CSP311需求说明.pdf",
        parent_path="docs",
        extension=".pdf",
        size=1,
        mtime=0.0,
        detected_codes=["202432--CSP311"],
    )
    assert score_project_match(record, project) >= 10


def test_parse_json_fallback_extracts_fields() -> None:
    raw = (
        '说明如下 {"project_id":"cv352-eu","project_name":"欧规系统",'
        '"confidence":0.81,"matched_by":"code","reason":"命中代号"} 完'
    )
    parsed = _parse_json(raw)
    assert parsed["project_id"] == "cv352-eu"
    assert parsed["confidence"] == 0.81
