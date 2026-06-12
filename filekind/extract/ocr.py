from __future__ import annotations

import os
import sys
import tempfile
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

_ocr_init_error: str | None = None
_OCR_TIMEOUT_SEC = int(os.environ.get("FILEKIND_OCR_TIMEOUT", "90"))
_ocr_progress: Callable[[str], None] | None = None
_paddle_lock = threading.Lock()
_paddle_engine: object | None = None

ProgressFn = Callable[[str], None]


def set_ocr_progress_callback(callback: ProgressFn | None) -> None:
    global _ocr_progress
    _ocr_progress = callback


def _say(message: str) -> None:
    if _ocr_progress is not None:
        _ocr_progress(message)


def ocr_importable() -> bool:
    try:
        import paddleocr  # noqa: F401

        return True
    except Exception as exc:
        global _ocr_init_error
        if _ocr_init_error is None:
            _ocr_init_error = str(exc)
        return False


def _vision_importable() -> bool:
    try:
        import ocrmac  # noqa: F401

        return True
    except ImportError:
        return False


def _resolve_backend() -> str | None:
    forced = os.environ.get("FILEKIND_OCR_BACKEND", "auto").strip().lower()
    if forced in {"off", "none", "0"}:
        return None
    if forced == "vision":
        return "vision" if _vision_importable() else None
    if forced == "paddle":
        return "paddle" if ocr_importable() else None
    if sys.platform == "darwin" and _vision_importable():
        return "vision"
    if ocr_importable():
        return "paddle"
    return None


def ocr_status_message() -> str:
    backend = _resolve_backend()
    if backend == "vision":
        return "macOS Vision（扫描 PDF/图片可用）"
    if backend == "paddle":
        return "PaddleOCR 已打包（首次 OCR 会下载中文模型到 ~/.paddleocr/）"
    if _ocr_init_error:
        return f"PaddleOCR 不可用: {_ocr_init_error}"
    if sys.platform == "darwin":
        return "OCR 未安装（请 pip install filekind[ocr]，含 macOS Vision 支持）"
    return "PaddleOCR 未安装（扫描 PDF/图片无法识别正文）"


def _configure_paddle_runtime() -> None:
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        os.environ.setdefault("PADDLE_SKIP_CHECK", "1")


def _ocr_with_vision(image_path: str) -> str:
    from ocrmac import ocrmac

    annotations = ocrmac.OCR(image_path).recognize()
    lines: list[str] = []
    for item in annotations:
        if not item or not item[0]:
            continue
        text = str(item[0]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _get_paddle_engine() -> object:
    global _paddle_engine
    with _paddle_lock:
        if _paddle_engine is not None:
            return _paddle_engine
        _say("  正在加载 OCR 模型（首次约 1～3 分钟，请稍候）…")
        _configure_paddle_runtime()
        from paddleocr import PaddleOCR

        _paddle_engine = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            show_log=False,
            use_gpu=False,
        )
        _say("  OCR 就绪，正在识别扫描页…")
        return _paddle_engine


def _run_paddle_ocr(engine: object, image_path: str) -> str:
    result = engine.ocr(image_path, cls=True)
    if not result or not result[0]:
        return ""
    lines: list[str] = []
    for line in result[0]:
        if line and len(line) >= 2 and line[1] and line[1][0]:
            lines.append(str(line[1][0]))
    return "\n".join(lines)


def _ocr_with_paddle(image_path: str, *, label: str | None = None) -> str:
    if label:
        _say(f"  正在 OCR：{label}")
    engine = _get_paddle_engine()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run_paddle_ocr, engine, image_path)
        try:
            return future.result(timeout=_OCR_TIMEOUT_SEC)
        except FuturesTimeoutError:
            _say(
                f"  OCR 超时（{_OCR_TIMEOUT_SEC} 秒），已跳过"
                f"{f'：{label}' if label else ''}"
            )
            return ""


def release_ocr() -> None:
    global _paddle_engine
    with _paddle_lock:
        _paddle_engine = None


def ocr_image_file(path: Path, *, label: str | None = None) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return ocr_image_bytes(data, label=label or path.name)


def ocr_image_bytes(image_bytes: bytes, *, label: str | None = None) -> str:
    backend = _resolve_backend()
    if backend is None:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        image_path = tmp.name

    try:
        if backend == "vision":
            if label:
                _say(f"  正在 OCR：{label}")
            return _ocr_with_vision(image_path)
        return _ocr_with_paddle(image_path, label=label)
    except Exception:
        return ""
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass
