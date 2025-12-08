# -*- coding: utf-8 -*-
"""Run the API server"""
import os
import sys

# 强制设置标准输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    # Windows: 设置标准输出为 UTF-8
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    else:
        # Python < 3.7 的兼容方案
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import signal
import time
import threading

import uvicorn

from app.api.main import app
from app.logger import logger


def print_welcome():
    """打印欢迎界面"""
    is_packaged = getattr(sys, 'frozen', False)
    
    print("\n" + "=" * 50)
    print(" " * 18 + "NeoChat API")
    print("=" * 50)
    
    if is_packaged:
        # Packaged mode: frontend served via FastAPI on port 8000
        print("\n  访问地址:  http://localhost:8000")
        print("\n  (打包模式 - 前后端统一端口)")
    else:
        # Development mode: API only (frontend managed by Electron or external)
        print("\n  Backend API:  http://localhost:8000")
        print("\n  (开发模式 - 仅启动 API 服务器)")
        print("  注意: 前端开发服务器由 Electron 或其他工具管理")
    
    print("\n" + "=" * 50 + "\n")


def run_backend():
    """在后台线程中运行后端服务器"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    # 启动后端服务器（在后台线程）
    logger.info("Starting NeoChat API server on http://0.0.0.0:8000")
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # 打印欢迎界面
    time.sleep(1)  # 给服务一点时间完成启动
    print_welcome()
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
