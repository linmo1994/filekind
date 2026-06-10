from pathlib import Path

import pytest
import yaml

from filekind.config import RunPathsError, load_config, resolve_run_paths


def test_default_paths_from_config(tmp_path: Path) -> None:
    src = tmp_path / "inbox"
    src.mkdir()
    cfg = tmp_path / "projects.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "paths": {"source": "inbox", "dest": "out"},
                "projects": [],
            }
        ),
        encoding="utf-8",
    )
    config = load_config(cfg)
    resolved_src, resolved_dest = resolve_run_paths(cfg, config, None, None)
    assert resolved_src == src.resolve()
    assert resolved_dest == (tmp_path / "out").resolve()
    assert resolved_dest.is_dir()


def test_auto_create_relative_source(tmp_path: Path) -> None:
    cfg = tmp_path / "projects.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {"paths": {"source": "待整理", "dest": "已整理"}, "projects": []}
        ),
        encoding="utf-8",
    )
    config = load_config(cfg)
    src, dest = resolve_run_paths(cfg, config, None, None)
    assert src == (tmp_path / "待整理").resolve()
    assert src.is_dir()
    assert dest == (tmp_path / "已整理").resolve()


def test_missing_absolute_source_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "projects.yaml"
    cfg.write_text(
        yaml.safe_dump(
            {
                "paths": {"source": "/no/such/inbox", "dest": "out"},
                "projects": [],
            }
        ),
        encoding="utf-8",
    )
    config = load_config(cfg)
    with pytest.raises(RunPathsError):
        resolve_run_paths(cfg, config, None, None)
