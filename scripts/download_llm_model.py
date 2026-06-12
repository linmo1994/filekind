#!/usr/bin/env python3
"""Download Qwen2.5-1.5B-Instruct Q4_K_M GGUF for local LLM classification."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
REPO_ID = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
REMOTE_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
LOCAL_FILENAME = "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
MIN_BYTES = 900_000_000
MIRROR_URL = (
    "https://hf-mirror.com/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    f"{REMOTE_FILENAME}"
)


def _download_via_curl(target: Path) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".partial")
    cmd = [
        "curl",
        "-L",
        "--retry",
        "5",
        "--retry-delay",
        "5",
        "-C",
        "-",
        "-o",
        str(partial),
        MIRROR_URL,
    ]
    print(f"Downloading via mirror: {MIRROR_URL}")
    subprocess.run(cmd, check=True)
    partial.rename(target)


def _download_via_hub(target: Path) -> None:
    from huggingface_hub import hf_hub_download

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co")
    print(f"Downloading via Hugging Face ({endpoint})…")
    downloaded = hf_hub_download(
        repo_id=REPO_ID,
        filename=REMOTE_FILENAME,
        local_dir=str(MODELS_DIR),
    )
    downloaded_path = Path(downloaded)
    if downloaded_path.resolve() != target.resolve():
        if target.exists():
            target.unlink()
        downloaded_path.rename(target)


def main() -> int:
    target = MODELS_DIR / LOCAL_FILENAME
    rel = f"models/{LOCAL_FILENAME}"

    if target.is_file() and target.stat().st_size >= MIN_BYTES:
        print(f"Already present: {target}")
        print(f"Configure in projects.yaml:\n  llm_gguf: {rel}")
        return 0

    try:
        _download_via_hub(target)
    except Exception as exc:
        print(f"Hugging Face download failed ({exc}); trying hf-mirror…", file=sys.stderr)
        try:
            _download_via_curl(target)
        except FileNotFoundError:
            print("curl not found; install curl or fix network access to Hugging Face.", file=sys.stderr)
            return 1
        except subprocess.CalledProcessError as curl_exc:
            print(f"Mirror download failed: {curl_exc}", file=sys.stderr)
            return 1

    if not target.is_file() or target.stat().st_size < MIN_BYTES:
        print(f"Download incomplete: {target}", file=sys.stderr)
        return 1

    print(f"Saved: {target} ({target.stat().st_size // (1024 * 1024)} MB)")
    print(f"Add to projects.yaml:\n  llm_gguf: {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
