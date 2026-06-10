from __future__ import annotations

from pathlib import Path

_ocr_engine = None
_ocr_unavailable = False


def _get_ocr():
    global _ocr_engine, _ocr_unavailable
    if _ocr_unavailable:
        return None
    if _ocr_engine is not None:
        return _ocr_engine
    try:
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        return _ocr_engine
    except Exception:
        _ocr_unavailable = True
        return None


def release_ocr() -> None:
    global _ocr_engine, _ocr_unavailable
    _ocr_engine = None


def ocr_image_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return ocr_image_bytes(data)


def ocr_image_bytes(image_bytes: bytes) -> str:
    engine = _get_ocr()
    if engine is None:
        return ""

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        tmp.write(image_bytes)
        tmp.flush()
        try:
            result = engine.ocr(tmp.name, cls=True)
        except Exception:
            return ""

    if not result or not result[0]:
        return ""

    lines: list[str] = []
    for line in result[0]:
        if line and len(line) >= 2 and line[1] and line[1][0]:
            lines.append(str(line[1][0]))
    return "\n".join(lines)
