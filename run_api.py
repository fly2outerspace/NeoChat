"""Run the API server with frontend"""
import os
import sys
import signal
import atexit
import subprocess
import time
import threading
import requests
from pathlib import Path

import uvicorn

from app.api.main import app
from app.logger import logger

# 全局变量存储前端进程和后端服务器
frontend_process = None
backend_server = None


def cleanup_frontend():
    """清理前端进程"""
    global frontend_process
    if frontend_process:
        try:
            logger.info("Stopping frontend server...")
            # Windows 使用 taskkill，Linux/Mac 使用 kill
            if sys.platform == "win32":
                # Windows: 终止进程树
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(frontend_process.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            else:
                # Linux/Mac: 发送 SIGTERM
                frontend_process.terminate()
                try:
                    frontend_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    frontend_process.kill()
            logger.info("Frontend server stopped")
        except Exception as e:
            logger.warning(f"Error stopping frontend: {e}")
        finally:
            frontend_process = None


def wait_for_backend(max_attempts=30, delay=1):
    """等待后端服务器就绪"""
    logger.info("Waiting for backend server to be ready...")
    for i in range(max_attempts):
        try:
            response = requests.get("http://localhost:8000/health", timeout=2)
            if response.status_code == 200:
                logger.info("Backend server is ready!")
                return True
        except Exception:
            pass
        time.sleep(delay)
        if i % 5 == 0 and i > 0:
            logger.info(f"Still waiting... ({i}/{max_attempts})")
    logger.error("Backend server failed to start within timeout")
    return False


def start_frontend():
    """启动前端开发服务器"""
    global frontend_process
    
    # 等待后端就绪
    if not wait_for_backend():
        logger.warning("Skipping frontend startup due to backend not ready.")
        return None
    
    frontend_dir = Path(__file__).parent / "frontend" / "web-chat"
    
    if not frontend_dir.exists():
        logger.warning(f"Frontend directory not found: {frontend_dir}")
        logger.warning("Skipping frontend startup. API server will run without frontend.")
        return None
    
    # 检查 package.json 是否存在
    package_json = frontend_dir / "package.json"
    if not package_json.exists():
        logger.warning("Frontend package.json not found.")
        logger.warning("Skipping frontend startup. API server will run without frontend.")
        return None
    
    # 检查 node_modules 是否存在
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        logger.warning("Frontend dependencies not installed.")
        logger.warning("To install: cd frontend/web-chat && pnpm install")
        logger.warning("Skipping frontend startup. API server will run without frontend.")
        return None
    
    try:
        logger.info("Starting frontend development server...")
        
        # 根据平台选择命令
        if sys.platform == "win32":
            cmd = ["pnpm", "dev"]
        else:
            cmd = ["pnpm", "dev"]
        
        # 启动前端进程
        frontend_process = subprocess.Popen(
            cmd,
            cwd=str(frontend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        
        # 等待一下，检查进程是否正常启动
        time.sleep(3)
        if frontend_process.poll() is not None:
            # 进程已经退出，说明启动失败
            output, _ = frontend_process.communicate()
            logger.error(f"Frontend failed to start. Output: {output}")
            frontend_process = None
            return None
        
        logger.info(f"Frontend server started (PID: {frontend_process.pid})")
        
        # 启动一个线程来读取前端输出（可选，用于调试）
        def log_frontend_output():
            if frontend_process and frontend_process.stdout:
                try:
                    for line in iter(frontend_process.stdout.readline, ''):
                        if line:
                            # 只记录错误和重要信息
                            if 'error' in line.lower() or 'Error' in line:
                                logger.warning(f"[Frontend] {line.strip()}")
                except Exception:
                    pass
        
        output_thread = threading.Thread(target=log_frontend_output, daemon=True)
        output_thread.start()
        
        return frontend_process
        
    except FileNotFoundError:
        # 如果是 Windows 且直接调用失败，尝试通过 cmd
        if sys.platform == "win32":
            try:
                logger.info("Trying to start frontend via cmd...")
                cmd = ["cmd", "/c", "pnpm", "dev"]
                frontend_process = subprocess.Popen(
                    cmd,
                    cwd=str(frontend_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )
                time.sleep(3)
                if frontend_process.poll() is not None:
                    output, _ = frontend_process.communicate()
                    logger.error(f"Frontend failed to start. Output: {output}")
                    frontend_process = None
                    return None
                logger.info(f"Frontend server started (PID: {frontend_process.pid})")
                
                def log_frontend_output():
                    if frontend_process and frontend_process.stdout:
                        try:
                            for line in iter(frontend_process.stdout.readline, ''):
                                if line:
                                    if 'error' in line.lower() or 'Error' in line:
                                        logger.warning(f"[Frontend] {line.strip()}")
                        except Exception:
                            pass
                output_thread = threading.Thread(target=log_frontend_output, daemon=True)
                output_thread.start()
                return frontend_process
            except Exception as e2:
                logger.warning(f"Failed to start frontend via cmd: {e2}")
                logger.warning("pnpm not found. Please install pnpm: npm install -g pnpm")
                logger.warning("Skipping frontend startup. API server will run without frontend.")
                return None
        else:
            logger.warning("pnpm not found. Please install pnpm: npm install -g pnpm")
            logger.warning("Skipping frontend startup. API server will run without frontend.")
            return None
    except Exception as e:
        logger.error(f"Failed to start frontend: {e}")
        logger.warning("Skipping frontend startup. API server will run without frontend.")
        return None


def signal_handler(signum, frame):
    """处理退出信号"""
    logger.info("Received shutdown signal, cleaning up...")
    cleanup_frontend()
    sys.exit(0)


def print_welcome():
    """打印欢迎界面"""
    is_packaged = getattr(sys, 'frozen', False)
    
    print("\n" + "=" * 50)
    print(" " * 18 + "NeoChat")
    print("=" * 50)
    
    if is_packaged:
        # Packaged mode: frontend served via FastAPI on port 8000
        print("\n  访问地址:  http://localhost:8000")
        print("\n  (打包模式 - 前后端统一端口)")
    else:
        # Development mode: separate frontend dev server
        print("\n  Backend API:  http://localhost:8000")
        print("  Frontend:     http://localhost:3000")
        print("\n  (开发模式 - 前后端分离)")
    
    print("\n" + "=" * 50 + "\n")


def run_backend():
    """在后台线程中运行后端服务器"""
    global backend_server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


if __name__ == "__main__":
    # 注册清理函数
    atexit.register(cleanup_frontend)
    
    # 注册信号处理器（用于 Ctrl+C 等）
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动后端服务器（在后台线程）
    logger.info("Starting NeoChat API server on http://0.0.0.0:8000")
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # 等待后端就绪后启动前端
    start_frontend()
    
    # 打印欢迎界面
    time.sleep(1)  # 给前端一点时间启动
    print_welcome()
    
    # 保持主线程运行
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        cleanup_frontend()
