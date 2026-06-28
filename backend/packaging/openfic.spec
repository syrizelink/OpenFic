# -*- mode: python ; coding: utf-8 -*-
"""OpenFic 后端 PyInstaller 打包配置（onedir）。

前置条件：
  - 前端已构建并复制到 backend/app/frontend_dist/（由 CI 完成）
执行方式（从 backend/ 目录）：
  pyinstaller packaging/openfic.spec
产物：dist/openfic-server/（可执行 + 依赖目录）
"""

import glob
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

BACKEND_ROOT = os.path.dirname(SPECPATH)  # backend/

datas: list = []
binaries: list = []
hiddenimports: list = []

# --- 复杂原生/动态导入包：收集全部子模块、数据、二进制 ---
_DYNAMIC_PACKAGES = [
    "langchain", "langchain_core", "langchain_community", "langgraph",
    "langchain_openai", "langchain_ollama", "langchain_anthropic",
    "langchain_google_genai", "langchain_mistralai", "langchain_groq",
    "langchain_deepseek", "langchain_cohere", "langchain_huggingface",
    "langchain_nvidia_ai_endpoints", "langchain_openrouter",
    "langchain_amazon_nova", "langgraph_checkpoint_sqlite",
    "lancedb", "fastembed", "onnxruntime", "tiktoken", "mem0ai",
    "aiocache", "argon2", "cryptography", "pyzmq", "fastembed",
]
for _pkg in _DYNAMIC_PACKAGES:
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

# --- app 包内非 .py 数据（prompts yaml 等），collect_data_files 递归收集 ---
datas += collect_data_files("app")

# --- Alembic 迁移 .py 脚本须以源码落盘供 Alembic 文件加载器读取 ---
_migrations_root = os.path.join(BACKEND_ROOT, "app", "storage", "migrations")
for _f in glob.glob(os.path.join(_migrations_root, "**", "*"), recursive=True):
    if os.path.isfile(_f):
        _rel = os.path.relpath(_f, BACKEND_ROOT)
        datas.append((_f, os.path.dirname(_rel)))

# --- alembic.ini ---
_alembic_ini = os.path.join(BACKEND_ROOT, "alembic.ini")
if os.path.isfile(_alembic_ini):
    datas.append((_alembic_ini, "."))

# --- 前端构建产物校验 ---
_frontend_dist = os.path.join(BACKEND_ROOT, "app", "frontend_dist")
if not os.path.isdir(_frontend_dist):
    sys.exit("前端构建产物缺失：请先构建前端并复制到 backend/app/frontend_dist/")

a = Analysis(
    [os.path.join(BACKEND_ROOT, "packaging", "server_main.py")],
    pathex=[BACKEND_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="openfic-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="openfic-server",
)
