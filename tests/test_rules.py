from pathlib import Path

import yaml

from filekind.classify.rules import apply_rules, collect_signals
from filekind.config import load_config
from filekind.models import FileRecord


def test_rule_code_match(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "projects": [
                    {
                        "id": "oms",
                        "name": "订单管理系统",
                        "aliases": ["OMS"],
                        "codes": ["SYS-OMS"],
                    }
                ],
                "code_patterns": ['(?i)SYS-[A-Z]+'],
            }
        ),
        encoding="utf-8",
    )
    config = load_config(config_path)
    record = FileRecord(
        path=str(tmp_path / "SYS-OMS_需求.pdf"),
        filename="SYS-OMS_需求.pdf",
        parent_path=str(tmp_path),
        extension=".pdf",
        size=1,
        mtime=0.0,
        raw_snippet="订单管理系统需求说明",
    )
    collect_signals(record, config)
    apply_rules(record, config)
    assert record.project_id == "oms"
    assert record.classified_by == "rule"
    assert record.matched_by == "code"
