# NeoChat Desktop Application Build Script
# Usage: .\build.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NeoChat Desktop Application Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check prerequisites
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Check Node.js
try {
    $nodeVersion = node --version
    Write-Host "  [OK] Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Node.js not installed, please install Node.js 18+" -ForegroundColor Red
    exit 1
}

# Check Python
try {
    $pythonVersion = python --version
    Write-Host "  [OK] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python not installed, please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Check PyInstaller
try {
    $pyinstallerVersion = pyinstaller --version
    Write-Host "  [OK] PyInstaller: $pyinstallerVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] PyInstaller not installed, please install: pip install pyinstaller" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: Build frontend
Write-Host "[2/6] Building frontend..." -ForegroundColor Yellow
Push-Location ..\frontend\web-chat

if (-not (Test-Path "node_modules")) {
    Write-Host "  Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host "  Building frontend..." -ForegroundColor Cyan
npm run build
npm run export

if (-not (Test-Path "out\index.html")) {
    Write-Host "  [ERROR] Frontend build failed, out/index.html not found" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "  [OK] Frontend build completed" -ForegroundColor Green
Pop-Location
Write-Host ""

# Step 3: Prepare backend
Write-Host "[3/6] Preparing backend..." -ForegroundColor Yellow

# Create backend directory
if (-not (Test-Path "backend")) {
    New-Item -ItemType Directory -Path "backend" | Out-Null
}

Write-Host "  Packaging backend with PyInstaller..." -ForegroundColor Cyan
Push-Location ..

# Clean old build files
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# Package backend
pyinstaller --onefile --name server --add-data "config;config" --add-data "app;app" --hidden-import=uvicorn --hidden-import=fastapi --hidden-import=app.api.main --hidden-import=app.storage.meilisearch_service --hidden-import=app.storage.database --hidden-import=app.storage.settings_database run_api.py

if (Test-Path "dist\server.exe") {
    Copy-Item "dist\server.exe" "electron\backend\server.exe" -Force
    Write-Host "  [OK] Backend packaged successfully" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Backend packaging failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location

# Handle Meilisearch
Write-Host "  Processing Meilisearch..." -ForegroundColor Cyan
if (-not (Test-Path "backend\meilisearch")) {
    New-Item -ItemType Directory -Path "backend\meilisearch" | Out-Null
}

$meilisearchSource = "meilisearch\meilisearch-windows-amd64.exe"
$meilisearchDest = "backend\meilisearch\meilisearch.exe"

if (Test-Path $meilisearchSource) {
    Copy-Item $meilisearchSource $meilisearchDest -Force
    Write-Host "  [OK] Meilisearch copied" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Meilisearch not found: $meilisearchSource" -ForegroundColor Yellow
    Write-Host "    Please place meilisearch-windows-amd64.exe in electron\meilisearch\ directory" -ForegroundColor Yellow
}

Write-Host ""

# Update config file
Write-Host "  Updating config file..." -ForegroundColor Cyan
if (-not (Test-Path "backend\config")) {
    New-Item -ItemType Directory -Path "backend\config" | Out-Null
}

$configSource = "..\config\config.toml"
$configDest = "backend\config\config.toml"

if (Test-Path $configSource) {
    Copy-Item $configSource $configDest -Force
    if (Test-Path "update_config.py") {
        python update_config.py $configDest 2>&1 | Out-Null
    }
    Write-Host "  [OK] Config file updated" -ForegroundColor Green
}

Write-Host ""

# Step 4: Check icon
Write-Host "[4/6] Checking application icon..." -ForegroundColor Yellow
if (-not (Test-Path "build\icon.ico")) {
    Write-Host "  [WARN] Icon file not found (build/icon.ico)" -ForegroundColor Yellow
    Write-Host "    Build will use default icon" -ForegroundColor Yellow
    Write-Host "    Recommended: prepare a 256x256 .ico file" -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Icon file exists" -ForegroundColor Green
}

Write-Host ""

# Step 5: Build Electron application
Write-Host "[5/6] Building Electron application..." -ForegroundColor Yellow

# Check and kill running NeoChat/Electron processes
Write-Host "  Checking for running NeoChat processes..." -ForegroundColor Cyan

# Use taskkill for more aggressive termination
try {
    taskkill /F /IM electron.exe /T 2>&1 | Out-Null
} catch { }

try {
    taskkill /F /IM NeoChat.exe /T 2>&1 | Out-Null
} catch { }

# Also try PowerShell method
$electronProcesses = Get-Process -Name "electron" -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID }
if ($electronProcesses) {
    Write-Host "  Found $($electronProcesses.Count) Electron process(es), terminating..." -ForegroundColor Yellow
    $electronProcesses | ForEach-Object {
        try {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        } catch { }
    }
}

# Kill processes by path (if they're in NeoChat directory)
Get-Process | Where-Object {
    $_.Path -and $_.Path -like "*NeoChat*"
} | Where-Object { $_.Id -ne $PID } | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    } catch { }
}

Start-Sleep -Seconds 3
Write-Host "  Process cleanup completed" -ForegroundColor Green

# Clean electron dist directory if it exists (to avoid file lock issues)
if (Test-Path "dist") {
    Write-Host "  Cleaning previous build..." -ForegroundColor Cyan
    
    # Try to remove win-unpacked directory first (most likely to be locked)
    if (Test-Path "dist\win-unpacked") {
        # Try multiple times with delays
        $removed = $false
        for ($i = 1; $i -le 3; $i++) {
            try {
                Remove-Item -Recurse -Force "dist\win-unpacked" -ErrorAction Stop
                $removed = $true
                Write-Host "  [OK] win-unpacked directory removed" -ForegroundColor Green
                break
            } catch {
                if ($i -lt 3) {
                    Write-Host "  Retry $i/3: Waiting before retry..." -ForegroundColor Yellow
                    Start-Sleep -Seconds 2
                    # Try killing processes again
                    taskkill /F /IM electron.exe /T 2>&1 | Out-Null
                    taskkill /F /IM NeoChat.exe /T 2>&1 | Out-Null
                } else {
                    Write-Host "  [WARN] Could not remove win-unpacked after 3 attempts" -ForegroundColor Yellow
                    Write-Host "    Please close any NeoChat windows and File Explorer windows showing this directory" -ForegroundColor Yellow
                    Write-Host "    electron-builder will attempt to handle it" -ForegroundColor Yellow
                }
            }
        }
    }
    
    # Try to remove installer files
    Get-ChildItem "dist\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue
        } catch { }
    }
}

Write-Host "  This may take a few minutes, please wait..." -ForegroundColor Cyan
npm run dist

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Electron build failed" -ForegroundColor Red
    exit 1
}

Write-Host "  [OK] Electron build completed" -ForegroundColor Green
Write-Host ""

# Step 6: Check output
Write-Host "[6/6] Checking build output..." -ForegroundColor Yellow
if (Test-Path "dist\*.exe") {
    $exeFile = Get-ChildItem "dist\*.exe" | Select-Object -First 1
    Write-Host "  [OK] Installer generated: $($exeFile.Name)" -ForegroundColor Green
    Write-Host "    Location: $($exeFile.FullName)" -ForegroundColor Cyan
    Write-Host "    Size: $([math]::Round($exeFile.Length / 1MB, 2)) MB" -ForegroundColor Cyan
} else {
    Write-Host "  [ERROR] Installer not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test installer: run dist\*.exe" -ForegroundColor White
Write-Host "  2. Test unpacked version: run dist\win-unpacked\NeoChat.exe" -ForegroundColor White
Write-Host "  3. See documentation: electron\RELEASE.md" -ForegroundColor White
Write-Host ""
