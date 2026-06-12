#!/usr/bin/env python3
"""Smoke-test a PyInstaller build by running --help without console encoding issues."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "filekind"
SYSTEM = DIST / "_系统"
SYSTEM_CONFIG = SYSTEM / "projects.yaml"


def _configure_stdio() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _safe_write(stream, text: str) -> None:
    try:
        stream.write(text)
        if not text.endswith("\n"):
            stream.write("\n")
        stream.flush()
    except UnicodeEncodeError:
        stream.buffer.write(text.encode("utf-8", errors="replace"))
        if not text.endswith("\n"):
            stream.buffer.write(b"\n")
        stream.buffer.flush()


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=str(cwd.resolve()),
    )


def _assert_config_found(output: str, config_path: Path) -> None:
    if "未找到默认配置文件 projects.yaml" in output:
        raise AssertionError(f"default config lookup failed:\n{output}")
    if str(config_path.resolve()) not in output:
        raise AssertionError(f"expected config path in output:\n{output}")


def main() -> int:
    _configure_stdio()
    platform = (sys.argv[1] if len(sys.argv) > 1 else sys.platform).lower()
    if platform in ("windows", "win32"):
        exe = DIST / "filekind.exe"
    else:
        exe = DIST / "filekind"

    if not exe.is_file():
        print(f"Missing binary: {exe}", file=sys.stderr)
        return 1

    if not SYSTEM_CONFIG.is_file():
        print(f"Missing bundled config: {SYSTEM_CONFIG}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    cwd = DIST.resolve()

    result = _run([str(exe.resolve()), "--help"], cwd=cwd, env=env)
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode != 0:
        _safe_write(sys.stderr, f"Smoke test failed with exit code {result.returncode}")
        if result.stdout:
            _safe_write(sys.stderr, f"stdout:\n{result.stdout[:2000]}")
        if result.stderr:
            _safe_write(sys.stderr, f"stderr:\n{result.stderr[:2000]}")
        return result.returncode

    print(f"OK: {exe.name} --help exited 0 ({len(output)} chars)")

    default_probe = _run([str(exe.resolve()), "validate-config"], cwd=cwd, env=env)
    default_output = (default_probe.stdout or "") + (default_probe.stderr or "")
    if default_probe.returncode != 0:
        print(default_output, file=sys.stderr)
        return default_probe.returncode
    _assert_config_found(default_output, SYSTEM_CONFIG)
    print("OK: frozen binary finds _系统/projects.yaml without -p")

    original = SYSTEM_CONFIG.read_text(encoding="utf-8")
    marker = "# smoke-test-marker\n"
    try:
        SYSTEM_CONFIG.write_text(marker + original, encoding="utf-8")
        edited_probe = _run([str(exe.resolve()), "validate-config"], cwd=cwd, env=env)
        edited_output = (edited_probe.stdout or "") + (edited_probe.stderr or "")
        if edited_probe.returncode != 0:
            print(edited_output, file=sys.stderr)
            return edited_probe.returncode
        _assert_config_found(edited_output, SYSTEM_CONFIG)
        print("OK: validate-config still works after editing _系统/projects.yaml")
    finally:
        SYSTEM_CONFIG.write_text(original, encoding="utf-8")

    dev_filekind = ROOT / ".venv" / "bin" / "filekind"
    if dev_filekind.is_file():
        root_cfg = DIST / "projects.yaml"
        if root_cfg.is_file():
            root_cfg.unlink()
        dev_probe = _run([str(dev_filekind.resolve()), "validate-config"], cwd=cwd, env=env)
        dev_output = (dev_probe.stdout or "") + (dev_probe.stderr or "")
        if dev_probe.returncode != 0:
            print(dev_output, file=sys.stderr)
            return dev_probe.returncode
        _assert_config_found(dev_output, SYSTEM_CONFIG)
        print("OK: dev filekind finds _系统/projects.yaml without -p")

    ocr_probe = _run(
        [
            str(exe.resolve()),
            "validate-config",
            "-p",
            str((SYSTEM / "projects.example.yaml").resolve()),
        ],
        cwd=cwd,
        env=env,
    )
    ocr_output = (ocr_probe.stdout or "") + (ocr_probe.stderr or "")
    if "OCR 未安装" in ocr_output:
        print("WARN: bundled binary reports OCR unavailable", file=sys.stderr)
        print(ocr_output[-500:], file=sys.stderr)
        return 1
    if "OCR" not in ocr_output and "Vision" not in ocr_output:
        print("WARN: validate-config missing OCR status line", file=sys.stderr)
        return 1
    print("OK: OCR appears available in frozen binary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
