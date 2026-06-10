"""Tests for user-editable classify_prompts.yaml loading."""

from pathlib import Path

import yaml

from filekind.models import AppConfig, PathsConfig
from filekind.prompts import (
    DEFAULT_MERGED_SYSTEM,
    default_classify_prompts,
    load_classify_prompts,
    resolve_classify_prompts_path,
)


def test_load_classify_prompts_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.write_text("paths:\n  classify_prompts: custom_prompts.yaml\n", encoding="utf-8")
    prompt_path = tmp_path / "custom_prompts.yaml"
    prompt_path.write_text(
        yaml.safe_dump(
            {
                "merged": {
                    "system": "自定义 system {summary_max_chars}",
                    "user": "自定义 user {filename}",
                }
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    config = AppConfig(paths=PathsConfig(classify_prompts="custom_prompts.yaml"))
    prompts = load_classify_prompts(config_path, config)

    assert prompts.source_path == prompt_path.resolve()
    assert prompts.merged_system == "自定义 system {summary_max_chars}"
    assert prompts.merged_user == "自定义 user {filename}"


def test_load_classify_prompts_falls_back_to_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.write_text("paths: {}\n", encoding="utf-8")
    config = AppConfig()

    prompts = load_classify_prompts(config_path, config)
    defaults = default_classify_prompts()

    assert prompts.source_path is None
    assert prompts.merged_system == defaults.merged_system
    assert prompts.merged_user == defaults.merged_user
    assert DEFAULT_MERGED_SYSTEM.startswith("你是文档归档组件")


def test_resolve_classify_prompts_path_beside_config(tmp_path: Path) -> None:
    config_path = tmp_path / "projects.yaml"
    config_path.touch()
    prompt_path = tmp_path / "classify_prompts.yaml"
    prompt_path.write_text("merged:\n  system: ok\n  user: ok\n", encoding="utf-8")

    resolved = resolve_classify_prompts_path(config_path, AppConfig())
    assert resolved == prompt_path.resolve()
