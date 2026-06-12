# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: build with `python scripts/run_pyinstaller.py`."""

import os

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import sys
from pathlib import Path

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        _reconfigure = getattr(_stream, "reconfigure", None)
        if callable(_reconfigure):
            try:
                _reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH)

fastembed_datas, fastembed_binaries, fastembed_hidden = collect_all("fastembed")
onnx_datas, onnx_binaries, onnx_hidden = collect_all("onnxruntime")
pymupdf_datas, pymupdf_binaries, pymupdf_hidden = collect_all("pymupdf")

llama_datas: list = []
llama_binaries: list = []
llama_hidden: list = []
try:
    llama_datas, llama_binaries, llama_hidden = collect_all("llama_cpp")
except Exception:
    pass

paddleocr_datas: list = []
paddleocr_binaries: list = []
paddleocr_hidden: list = []
paddle_datas: list = []
paddle_binaries: list = []
paddle_hidden: list = []
cython_datas: list = []
cython_binaries: list = []
cython_hidden: list = []
ocrmac_datas: list = []
ocrmac_binaries: list = []
ocrmac_hidden: list = []
try:
    paddleocr_datas, paddleocr_binaries, paddleocr_hidden = collect_all("paddleocr")
    paddle_datas, paddle_binaries, paddle_hidden = collect_all("paddle")
    cython_datas, cython_binaries, cython_hidden = collect_all("Cython")
except Exception:
    pass
try:
    ocrmac_datas, ocrmac_binaries, ocrmac_hidden = collect_all("ocrmac")
except Exception:
    pass

hiddenimports = (
    collect_submodules("filekind")
    + collect_submodules("typer")
    + collect_submodules("click")
    + fastembed_hidden
    + onnx_hidden
    + pymupdf_hidden
    + llama_hidden
    + paddleocr_hidden
    + paddle_hidden
    + cython_hidden
    + ocrmac_hidden
    + [
        "yaml",
        "docx",
        "pptx",
        "openpyxl",
        "numpy",
        "loguru",
        "huggingface_hub",
        "tokenizers",
        "pyclipper",
        "shapely",
        "skimage",
        "lmdb",
        "apted",
        "onnx",
    ]
)

datas = (
    [(str(root / "projects.example.yaml"), ".")]
    + [(str(root / "classify_prompts.example.yaml"), ".")]
    + fastembed_datas
    + onnx_datas
    + pymupdf_datas
    + llama_datas
    + paddleocr_datas
    + paddle_datas
    + cython_datas
    + ocrmac_datas
)

binaries = (
    fastembed_binaries
    + onnx_binaries
    + pymupdf_binaries
    + llama_binaries
    + paddleocr_binaries
    + paddle_binaries
    + cython_binaries
    + ocrmac_binaries
)

a = Analysis(
    ["filekind_main.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "scripts" / "pyi_rth_paddle.py")],
    excludes=[
        "torch",
        "tensorflow",
        "matplotlib",
        "pytest",
        "tensorrt",
        "tkinter",
        "_tkinter",
        "PIL.SpiderImagePlugin",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="filekind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="filekind",
)
