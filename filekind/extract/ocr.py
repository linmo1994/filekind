from __future__ import annotations

import multiprocessing as mp
import os
import sys
import tempfile
from pathlib import Path

_ocr_init_error: str | None = None
_OCR_TIMEOUT_SEC = int(os.environ.get("FILEKIND_OCR_TIMEOUT", "90"))


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


def _paddle_worker(image_path: str, out_queue: mp.Queue) -> None:
    try:
        _configure_paddle_runtime()
        from paddleocr import PaddleOCR

        engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False, use_gpu=False)
        result = engine.ocr(image_path, cls=True)
    except Exception:
        out_queue.put("")
        return

    if not result or not result[0]:
        out_queue.put("")
        return

    lines: list[str] = []
    for line in result[0]:
        if line and len(line) >= 2 and line[1] and line[1][0]:
            lines.append(str(line[1][0]))
    out_queue.put("\n".join(lines))


def _ocr_with_paddle(image_path: str) -> str:
    ctx = mp.get_context("spawn")
    out_queue: mp.Queue = ctx.Queue(maxsize=1)
    proc = ctx.Process(target=_paddle_worker, args=(image_path, out_queue))
    proc.start()
    proc.join(_OCR_TIMEOUT_SEC)
    if proc.is_alive():
        proc.terminate()
        proc.join(5)
        return ""
    if out_queue.empty():
        return ""
    return out_queue.get_nowait() or ""


def release_ocr() -> None:
    return


def ocr_image_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return ocr_image_bytes(data)


def ocr_image_bytes(image_bytes: bytes) -> str:
    backend = _resolve_backend()
    if backend is None:
        return ""

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        image_path = tmp.name

    try:
        if backend == "vision":
            return _ocr_with_vision(image_path)
        return _ocr_with_paddle(image_path)
    except Exception:
        return ""
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass
