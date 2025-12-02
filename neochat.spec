# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for NeoChat

This configuration bundles:
- Python backend (FastAPI + all dependencies)
- Frontend static files (Next.js built output)
- Configuration files

Usage:
1. Build frontend: cd frontend/web-chat && pnpm build
2. Run PyInstaller: pyinstaller neochat.spec
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# Get the project root directory
project_root = Path(SPECPATH)

# Check if frontend is built
frontend_out = project_root / "frontend" / "web-chat" / "out"
if not frontend_out.exists():
    print("WARNING: Frontend not built! Run 'cd frontend/web-chat && pnpm build' first.")
    print("Continuing without frontend...")
    frontend_datas = []
else:
    # Include frontend static files
    frontend_datas = [
        (str(frontend_out), 'frontend'),
    ]

# Data files to include
datas = [
    # Configuration directory
    ('config', 'config'),
    # Add frontend if available
    *frontend_datas,
]

# Collect all data from key packages
packages_to_collect = [
    'uvicorn',
    'fastapi', 
    'starlette',
    'pydantic',
    'pydantic_core',
    'openai',
    'httpx',
    'meilisearch',
    'anyio',
    'sniffio',
    'h11',
    'httpcore',
    'ddgs',
    'bs4',
    'tenacity',
    'fake_useragent',  # Required for DuckDuckGo search
    'loguru',          # Logging library
]

binaries = []
hiddenimports = []

for package in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
        datas.extend(pkg_datas)
        binaries.extend(pkg_binaries)
        hiddenimports.extend(pkg_hiddenimports)
        print(f"Collected package: {package}")
    except Exception as e:
        print(f"Warning: Could not collect {package}: {e}")

# Additional hidden imports
additional_hiddenimports = [
    # Email modules
    'email.mime.text',
    'email.mime.multipart',
    # Uvicorn internals
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
    # FastAPI and Starlette
    'fastapi',
    'fastapi.staticfiles',
    'fastapi.middleware',
    'fastapi.middleware.cors',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.base',
    'starlette.middleware.cors',
    'starlette.staticfiles',
    'starlette.responses',
    'starlette.requests',
    # Pydantic
    'pydantic',
    'pydantic.fields',
    'pydantic_core',
    'pydantic_core._pydantic_core',
    # OpenAI
    'openai',
    'openai.resources',
    # HTTP clients
    'httpx',
    'httpx._transports',
    'httpcore',
    'h11',
    # Async
    'asyncio',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
    'sniffio',
    # Database
    'sqlite3',
    # Meilisearch
    'meilisearch',
    'meilisearch.errors',
    'meilisearch.index',
    'meilisearch.client',
    # Encryption
    'cryptography',
    'cryptography.fernet',
    # Web search
    'ddgs',
    'requests',
    'bs4',
    'beautifulsoup4',
    # JSON
    'json',
    # Multipart
    'multipart',
    'python_multipart',
]

hiddenimports.extend(additional_hiddenimports)

# Collect all app modules
app_modules = []
for root, dirs, files in os.walk(str(project_root / 'app')):
    for file in files:
        if file.endswith('.py'):
            module_path = os.path.join(root, file)
            rel_path = os.path.relpath(module_path, str(project_root))
            module_name = rel_path.replace(os.sep, '.').replace('.py', '')
            app_modules.append(module_name)

hiddenimports.extend(app_modules)

# Remove duplicates
hiddenimports = list(set(hiddenimports))

# Analysis
a = Analysis(
    ['run_api.py'],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'jupyter',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove unnecessary files to reduce size
a.binaries = [x for x in a.binaries if not x[0].startswith('libopenblas')]
a.binaries = [x for x in a.binaries if not x[0].startswith('libnvrtc')]

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeoChat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True to see console output for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add your icon path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeoChat',
)
