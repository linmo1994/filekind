# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: build with `pyinstaller filekind.spec`."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH)

fastembed_datas, fastembed_binaries, fastembed_hidden = collect_all("fastembed")
onnx_datas, onnx_binaries, onnx_hidden = collect_all("onnxruntime")
pymupdf_datas, pymupdf_binaries, pymupdf_hidden = collect_all("pymupdf")

hiddenimports = (
    collect_submodules("filekind")
    + collect_submodules("typer")
    + collect_submodules("click")
    + fastembed_hidden
    + onnx_hidden
    + pymupdf_hidden
    + [
        "yaml",
        "docx",
        "pptx",
        "openpyxl",
        "numpy",
        "loguru",
        "huggingface_hub",
        "tokenizers",
    ]
)

datas = (
    [(str(root / "projects.example.yaml"), ".")]
    + [(str(root / "classify_prompts.example.yaml"), ".")]
    + fastembed_datas
    + onnx_datas
    + pymupdf_datas
)

binaries = fastembed_binaries + onnx_binaries + pymupdf_binaries

a = Analysis(
    ["filekind_main.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "paddleocr",
        "paddle",
        "paddlepaddle",
        "llama_cpp",
        "torch",
        "tensorflow",
        "matplotlib",
        "pytest",
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
