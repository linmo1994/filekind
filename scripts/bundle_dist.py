#!/usr/bin/env python3
"""Stage config templates and inbox folders into dist/filekind after PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "filekind"
SYSTEM = DIST / "_系统"
LLM_FILENAME = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"


def _dylib_arch(path: Path) -> str | None:
    try:
        out = subprocess.check_output(["file", str(path)], text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return None
    if "arm64" in out:
        return "arm64"
    if "x86_64" in out:
        return "x86_64"
    return None


def _fix_macos_scipy_dylib_conflicts() -> None:
    """Paddle's collect_all can drop x86_64 Fortran libs at _internal root.

    Scipy extensions resolve @rpath against those before scipy/.dylibs, which
    breaks PaddleOCR import on Apple Silicon. Prefer scipy's arm64 copies.
    """
    if sys.platform != "darwin":
        return

    internal = DIST / "_internal"
    scipy_dylibs = internal / "scipy" / ".dylibs"
    if not scipy_dylibs.is_dir():
        return

    fixed: list[str] = []
    for src in sorted(scipy_dylibs.glob("*.dylib")):
        dst = internal / src.name
        if not dst.is_file():
            continue
        src_arch = _dylib_arch(src)
        dst_arch = _dylib_arch(dst)
        if src_arch and dst_arch and src_arch != dst_arch:
            shutil.copy2(src, dst)
            fixed.append(dst.name)

    if fixed:
        print(f"Fixed macOS dylib arch conflicts: {', '.join(fixed)}")


def _link_llm_model() -> None:
    src = ROOT / "models" / LLM_FILENAME
    dst_dir = SYSTEM / "models"
    dst = dst_dir / LLM_FILENAME

    if not src.is_file():
        if dst.is_file():
            print(f"LLM model present: {dst}")
        else:
            print(
                "LLM: run scripts/download_llm_model.py, then re-run build "
                "(or copy GGUF into dist/filekind/_系统/models/)"
            )
        return

    dst_dir.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() and dst.resolve() == src.resolve():
            print(f"LLM model linked: {dst}")
            return
        if dst.is_file() and not dst.is_symlink() and dst.stat().st_size >= src.stat().st_size:
            print(f"LLM model present: {dst}")
            return
        dst.unlink()

    try:
        dst.symlink_to(src.resolve())
        print(f"Linked LLM model: {dst} -> {src}")
    except OSError:
        print(f"Could not symlink model; copy manually to {dst}")


def _stage_system_files() -> None:
    SYSTEM.mkdir(parents=True, exist_ok=True)
    for name in (
        "projects.example.yaml",
        "classify_prompts.example.yaml",
        "classify_prompts.example.txt",
    ):
        src = ROOT / name
        dst = SYSTEM / name
        shutil.copy2(src, dst)
        if name.endswith(".example.yaml"):
            shutil.copy2(src, SYSTEM / name.replace(".example", ""))
        elif name.endswith(".example.txt"):
            shutil.copy2(src, SYSTEM / name.replace(".example", ""))


def main() -> int:
    if sys.platform == "win32":
        binary = DIST / "filekind.exe"
    else:
        binary = DIST / "filekind"

    if not binary.is_file():
        print(f"Build output not found: {binary}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)

    usage_src = ROOT / "使用说明.txt"
    if usage_src.is_file():
        shutil.copy2(usage_src, DIST / "使用说明.txt")

    _stage_system_files()

    for folder in ("待整理", "已整理", "项目清单"):
        (DIST / folder).mkdir(parents=True, exist_ok=True)

    _link_llm_model()
    _fix_macos_scipy_dylib_conflicts()

    if sys.platform == "darwin":
        launcher = ROOT / "scripts" / "双击可整理文件.command"
        if launcher.is_file():
            target = DIST / launcher.name
            shutil.copy2(launcher, target)
            target.chmod(0o755)
    elif sys.platform == "win32":
        launcher = ROOT / "scripts" / "run-filekind.bat"
        if launcher.is_file():
            shutil.copy2(launcher, DIST / launcher.name)

    print(f"Bundle ready: {DIST}")
    print(f"  Clerk area: 待整理/, 已整理/, 项目清单/")
    print(f"  System area: {SYSTEM}/")
    print(f"Binary: {binary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
