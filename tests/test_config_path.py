from pathlib import Path

import pytest

from filekind.config import resolve_config_path


def test_resolve_config_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "projects.yaml"
    cfg.write_text("projects: []\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert resolve_config_path(None) == cfg.resolve()


def test_explicit_path_overrides(tmp_path: Path) -> None:
    cfg = tmp_path / "custom.yaml"
    cfg.write_text("projects: []\n", encoding="utf-8")
    assert resolve_config_path(cfg) == cfg.resolve()


def test_frozen_bundle_prefers_executable_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    cwd_cfg = tmp_path / "projects.yaml"
    bundle_cfg = bundle / "projects.yaml"
    cwd_cfg.write_text("paths:\n  source: cwd-inbox\n", encoding="utf-8")
    bundle_cfg.write_text("paths:\n  source: bundle-inbox\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("filekind.config.bundle_root", lambda: bundle)
    monkeypatch.setattr("filekind.config.is_frozen_bundle", lambda: True)
    assert resolve_config_path(None) == bundle_cfg.resolve()
