#!/usr/bin/env python3
"""Smoke-test a PyInstaller build by running --help without console encoding issues."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


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


def main() -> int:
    _configure_stdio()
    platform = (sys.argv[1] if len(sys.argv) > 1 else sys.platform).lower()
    if platform in ("windows", "win32"):
        exe = Path("dist/filekind/filekind.exe")
    else:
        exe = Path("dist/filekind/filekind")

    if not exe.is_file():
        print(f"Missing binary: {exe}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("NO_COLOR", "1")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    result = subprocess.run(
        [str(exe.resolve()), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    output = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        print(f"OK: {exe.name} --help exited 0 ({len(output)} chars)")
        ocr_probe = subprocess.run(
            [
                str(exe.resolve()),
                "validate-config",
                "-p",
                str(Path("dist/filekind/projects.example.yaml").resolve()),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(Path("dist/filekind").resolve()),
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

    _safe_write(sys.stderr, f"Smoke test failed with exit code {result.returncode}")
    if result.stdout:
        _safe_write(sys.stderr, f"stdout:\n{result.stdout[:2000]}")
    if result.stderr:
        _safe_write(sys.stderr, f"stderr:\n{result.stderr[:2000]}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
