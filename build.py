#!/usr/bin/env python
"""
NeoChat Build Script

This script automates the build process:
1. Build frontend (Next.js static export)
2. Package with PyInstaller

Usage:
    python build.py          # Full build (frontend + package)
    python build.py --skip-frontend  # Skip frontend build
    python build.py --help   # Show help

Requirements:
    - Python 3.8+
    - Node.js 18+ with pnpm
    - PyInstaller (pip install pyinstaller)
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path


def print_step(step: str):
    """Print a build step header"""
    print(f"\n{'='*60}")
    print(f"  {step}")
    print(f"{'='*60}\n")


def run_command(cmd: list, cwd: str = None, check: bool = True) -> bool:
    """Run a command and return success status"""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=False,
            text=True,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Command failed with return code {e.returncode}")
        return False
    except FileNotFoundError as e:
        print(f"Command not found: {e}")
        return False


def check_requirements() -> bool:
    """Check if all required tools are installed"""
    print_step("Checking Requirements")
    
    requirements_ok = True
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8+ is required")
        requirements_ok = False
    else:
        print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("ERROR: PyInstaller not installed. Run: pip install pyinstaller")
        requirements_ok = False
    
    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js {result.stdout.strip()}")
        else:
            print("ERROR: Node.js not found")
            requirements_ok = False
    except FileNotFoundError:
        print("ERROR: Node.js not found. Please install Node.js 18+")
        requirements_ok = False
    
    # Check pnpm
    try:
        result = subprocess.run(["pnpm", "--version"], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✓ pnpm {result.stdout.strip()}")
        else:
            print("WARNING: pnpm not found, will try npm")
    except FileNotFoundError:
        print("WARNING: pnpm not found, will try npm")
    
    return requirements_ok


def build_frontend(project_root: Path) -> bool:
    """Build the frontend using Next.js static export"""
    print_step("Building Frontend")
    
    frontend_dir = project_root / "frontend" / "web-chat"
    
    if not frontend_dir.exists():
        print(f"ERROR: Frontend directory not found: {frontend_dir}")
        return False
    
    # Check if node_modules exists
    node_modules = frontend_dir / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...")
        # Try pnpm first, then npm
        if not run_command(["pnpm", "install"], cwd=str(frontend_dir), check=False):
            print("pnpm failed, trying npm...")
            if not run_command(["npm", "install"], cwd=str(frontend_dir)):
                print("ERROR: Failed to install frontend dependencies")
                return False
    
    # Build frontend
    print("Building frontend...")
    # Try pnpm first, then npm
    if not run_command(["pnpm", "build"], cwd=str(frontend_dir), check=False):
        print("pnpm failed, trying npm...")
        if not run_command(["npm", "run", "build"], cwd=str(frontend_dir)):
            print("ERROR: Failed to build frontend")
            return False
    
    # Verify output
    out_dir = frontend_dir / "out"
    if not out_dir.exists() or not (out_dir / "index.html").exists():
        print(f"ERROR: Frontend build output not found: {out_dir}")
        return False
    
    print(f"✓ Frontend built successfully: {out_dir}")
    return True


def build_package(project_root: Path) -> bool:
    """Package the application using PyInstaller"""
    print_step("Packaging with PyInstaller")
    
    spec_file = project_root / "neochat.spec"
    if not spec_file.exists():
        print(f"ERROR: Spec file not found: {spec_file}")
        return False
    
    # Clean previous build
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"
    
    if build_dir.exists():
        print(f"Cleaning build directory: {build_dir}")
        shutil.rmtree(build_dir)
    
    if dist_dir.exists():
        print(f"Cleaning dist directory: {dist_dir}")
        shutil.rmtree(dist_dir)
    
    # Run PyInstaller
    if not run_command(["pyinstaller", str(spec_file), "--clean"], cwd=str(project_root)):
        print("ERROR: PyInstaller build failed")
        return False
    
    # Verify output
    exe_path = dist_dir / "NeoChat" / "NeoChat.exe"
    if not exe_path.exists():
        print(f"ERROR: Executable not found: {exe_path}")
        return False
    
    print(f"✓ Package built successfully: {dist_dir / 'NeoChat'}")
    return True


def copy_additional_files(project_root: Path) -> bool:
    """Copy additional files needed for distribution"""
    print_step("Copying Additional Files")
    
    dist_dir = project_root / "dist" / "NeoChat"
    
    if not dist_dir.exists():
        print(f"ERROR: Dist directory not found: {dist_dir}")
        return False
    
    # Files to copy
    files_to_copy = [
        # (source, destination_name)
        # Config is already included via spec file
    ]
    
    # Create data directory for runtime data
    data_dir = dist_dir / "data"
    data_dir.mkdir(exist_ok=True)
    print(f"✓ Created data directory: {data_dir}")
    
    # Copy README for distribution
    readme_content = """# NeoChat

## 快速开始

1. 双击 `NeoChat.exe` 启动程序
2. 程序会自动启动后端服务和 Meilisearch 搜索引擎
3. 打开浏览器访问 http://localhost:8000

## 配置

编辑 `config/config.toml` 文件来配置：
- Meilisearch 路径和设置
- 其他应用配置

## 注意事项

- 首次运行时，请确保 Meilisearch 可执行文件路径配置正确
- 数据文件存储在 `data/` 目录中
- 日志输出在控制台窗口中

## 问题排查

如果遇到问题：
1. 检查控制台输出的错误信息
2. 确认 config/config.toml 配置正确
3. 确认 Meilisearch 可执行文件存在

"""
    
    readme_path = dist_dir / "README.txt"
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"✓ Created README: {readme_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="NeoChat Build Script")
    parser.add_argument(
        "--skip-frontend",
        action="store_true",
        help="Skip frontend build (use existing build)"
    )
    parser.add_argument(
        "--skip-package",
        action="store_true", 
        help="Skip PyInstaller packaging (only build frontend)"
    )
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.resolve()
    print(f"Project root: {project_root}")
    
    # Check requirements
    if not check_requirements():
        print("\nERROR: Requirements check failed. Please install missing dependencies.")
        sys.exit(1)
    
    # Build frontend
    if not args.skip_frontend:
        if not build_frontend(project_root):
            print("\nERROR: Frontend build failed")
            sys.exit(1)
    else:
        print("\nSkipping frontend build...")
        # Verify frontend exists
        frontend_out = project_root / "frontend" / "web-chat" / "out"
        if not frontend_out.exists():
            print(f"WARNING: Frontend not found at {frontend_out}")
            print("The package will run in API-only mode.")
    
    # Package with PyInstaller
    if not args.skip_package:
        if not build_package(project_root):
            print("\nERROR: Packaging failed")
            sys.exit(1)
        
        # Copy additional files
        if not copy_additional_files(project_root):
            print("\nWARNING: Failed to copy some additional files")
    else:
        print("\nSkipping packaging...")
    
    # Success
    print_step("Build Complete!")
    
    if not args.skip_package:
        dist_dir = project_root / "dist" / "NeoChat"
        print(f"Output directory: {dist_dir}")
        print(f"\nTo run the packaged application:")
        print(f"  cd {dist_dir}")
        print(f"  .\\NeoChat.exe")
    
    print("\nDone!")


if __name__ == "__main__":
    main()

