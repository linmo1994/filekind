from pathlib import Path

import pytest

from filekind.config import (
    DEFAULT_CONFIG_NAME,
    SYSTEM_DIR_NAME,
    migrate_legacy_bundle_layout,
    paths_base_dir,
    resolve_config_path,
    resolve_run_paths,
    state_dir,
)
from filekind.config import load_config


def test_resolve_config_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "projects.yaml"
    cfg.write_text("projects: []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert resolve_config_path(None) == cfg.resolve()


def test_explicit_path_overrides(tmp_path: Path) -> None:
    cfg = tmp_path / "custom.yaml"
    cfg.write_text("projects: []\n", encoding="utf-8")
    assert resolve_config_path(cfg) == cfg.resolve()


def test_frozen_bundle_prefers_system_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    system = bundle / SYSTEM_DIR_NAME
    system.mkdir(parents=True)
    cwd_cfg = tmp_path / "projects.yaml"
    legacy_bundle_cfg = bundle / "projects.yaml"
    system_cfg = system / "projects.yaml"
    cwd_cfg.write_text("paths:\n  source: cwd-inbox\n", encoding="utf-8")
    legacy_bundle_cfg.write_text("paths:\n  source: legacy-bundle-inbox\n", encoding="utf-8")
    system_cfg.write_text("paths:\n  source: system-inbox\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("filekind.config.bundle_root", lambda: bundle)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: True)
    assert resolve_config_path(None) == system_cfg.resolve()


def test_migrate_legacy_bundle_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "projects.yaml").write_text("projects: []\n", encoding="utf-8")
    (bundle / "classify_prompts.txt").write_text("prompt\n", encoding="utf-8")
    models = bundle / "models"
    models.mkdir()
    (models / "test.gguf").write_text("x", encoding="utf-8")
    legacy_state = bundle / ".filekind"
    legacy_state.mkdir()
    (legacy_state / "last_inventory.txt").write_text("/tmp/x.xlsx", encoding="utf-8")

    monkeypatch.setattr("filekind.config.bundle_root", lambda: bundle)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: True)

    migrate_legacy_bundle_layout(bundle)

    system = bundle / SYSTEM_DIR_NAME
    assert (system / "projects.yaml").is_file()
    assert not (bundle / "projects.yaml").exists()
    assert (system / "classify_prompts.txt").is_file()
    assert (system / "models" / "test.gguf").is_file()
    assert (system / ".state" / "last_inventory.txt").is_file()
    assert not legacy_state.exists()


def test_dev_mode_finds_system_dir_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    system = bundle / SYSTEM_DIR_NAME
    system.mkdir(parents=True)
    cfg = system / "projects.yaml"
    cfg.write_text("projects: []\n", encoding="utf-8")
    monkeypatch.chdir(bundle)
    monkeypatch.setattr("filekind.config.bundle_root", lambda: None)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: False)
    assert resolve_config_path(None) == cfg.resolve()


def test_bootstrap_config_from_system_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    system = bundle / SYSTEM_DIR_NAME
    system.mkdir(parents=True)
    example = system / "projects.example.yaml"
    example.write_text("projects: []\n", encoding="utf-8")
    monkeypatch.chdir(bundle)
    monkeypatch.setattr("filekind.config.bundle_root", lambda: None)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: False)
    resolved = resolve_config_path(None)
    assert resolved == (system / "projects.yaml").resolve()
    assert resolved.is_file()


def test_frozen_bundle_bootstraps_from_internal_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    internal = bundle / "_internal"
    system = bundle / SYSTEM_DIR_NAME
    internal.mkdir(parents=True)
    system.mkdir(parents=True)
    example = internal / "projects.example.yaml"
    example.write_text("paths:\n  source: inbox\nprojects: []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("filekind.config.bundle_root", lambda: bundle)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: True)
    monkeypatch.setattr(
        "filekind.config.internal_bundle_dir",
        lambda: internal,
    )

    resolved = resolve_config_path(None)
    assert resolved == (system / "projects.yaml").resolve()
    assert resolved.read_text(encoding="utf-8").startswith("paths:")


def test_run_paths_use_app_root_when_config_in_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    system = bundle / SYSTEM_DIR_NAME
    inbox = bundle / "待整理"
    outbox = bundle / "已整理"
    system.mkdir(parents=True)
    inbox.mkdir()
    outbox.mkdir()

    cfg = system / DEFAULT_CONFIG_NAME
    cfg.write_text(
        "paths:\n  source: 待整理\n  dest: 已整理\nprojects: []\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("filekind.config.bundle_root", lambda: bundle)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: True)

    config = load_config(cfg)
    src, dst = resolve_run_paths(cfg, config, create_dest=False, create_relative_source=False)
    assert src == inbox.resolve()
    assert dst == outbox.resolve()
    assert paths_base_dir(cfg) == bundle.resolve()
    assert state_dir(cfg) == (system / ".state").resolve()
