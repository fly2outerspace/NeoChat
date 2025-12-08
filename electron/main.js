const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const iconv = require('iconv-lite');
const { ipcMain } = require('electron');
const treeKill = require('tree-kill');
const fs = require('fs');

// 判断是否为开发模式：既不是打包应用，且 NODE_ENV 不是 production
const isDev = !app.isPackaged && process.env.NODE_ENV !== 'production';
const rendererDevURL = 'http://localhost:3000';

// 获取应用程序图标路径
function getIconPath() {
  // 开发模式：从 build 目录读取
  if (!app.isPackaged) {
    const iconPath = path.join(__dirname, 'build', 'icon.ico');
    if (fs.existsSync(iconPath)) {
      return iconPath;
    }
  } else {
    // 打包环境：尝试从多个可能的位置读取图标
    // electron-builder 可能将图标放在 resources 目录
    const possiblePaths = [
      path.join(process.resourcesPath, 'icon.ico'),
      path.join(process.resourcesPath, 'build', 'icon.ico'),
      path.join(path.dirname(process.execPath), 'icon.ico'),
    ];
    
    for (const iconPath of possiblePaths) {
      if (fs.existsSync(iconPath)) {
        return iconPath;
      }
    }
    
    // 如果找不到，返回 null，Electron 会使用 exe 内置的图标
    // electron-builder 已经将图标嵌入到 exe 中
    return null;
  }
  return null;
}

// 获取前端静态文件路径
// 在打包应用中，前端静态文件被复制到 resources/frontend（out 目录的内容直接复制到 frontend）
function getRendererProdPath() {
  if (app.isPackaged) {
    const htmlPath = path.join(process.resourcesPath, 'frontend', 'index.html');
    debugLog(`[Renderer] Resolved HTML path (resources): ${htmlPath}`);
    debugLog(`[Renderer] File exists: ${fs.existsSync(htmlPath)}`);
    return htmlPath;
  } else {
    // 开发模式：从 __dirname 向上查找
    return path.join(__dirname, '../frontend/web-chat/out/index.html');
  }
}

const rendererProdPath = getRendererProdPath();
const API_URL = 'http://localhost:8000';
const API_HEALTH_CHECK_URL = `${API_URL}/health`;

// 进程管理器：统一管理所有子进程
class ProcessManager {
  constructor() {
    this.processes = new Map(); // name -> { process, type, pid }
    this.quitting = false;
  }

  // 注册进程
  register(name, process, type = 'unknown') {
    if (this.processes.has(name)) {
      console.warn(`[ProcessManager] Process ${name} already registered, replacing...`);
      this.kill(name);
    }
    this.processes.set(name, { process, type, pid: process.pid });
    console.log(`[ProcessManager] Registered ${type} process: ${name} (PID: ${process.pid})`);
  }

  // 获取进程
  get(name) {
    const entry = this.processes.get(name);
    return entry ? entry.process : null;
  }

  // 优雅关闭单个进程
  async kill(name, timeout = 5000) {
    const entry = this.processes.get(name);
    if (!entry) {
      return Promise.resolve();
    }

    const { process, type } = entry;
    console.log(`[ProcessManager] Stopping ${type} process: ${name} (PID: ${process.pid})...`);

    return new Promise((resolve) => {
      // 检查进程是否已经退出
      if (process.killed || process.exitCode !== null) {
        this.processes.delete(name);
        resolve();
        return;
      }

      let resolved = false;
      const cleanup = () => {
        if (resolved) return;
        resolved = true;
        this.processes.delete(name);
        resolve();
      };

      // 监听进程退出
      process.once('exit', () => {
        console.log(`[ProcessManager] Process ${name} exited gracefully`);
        cleanup();
      });

      // 先尝试优雅关闭
      try {
        // 使用 tree-kill 跨平台发送 SIGTERM（会终止整个进程树）
        treeKill(process.pid, 'SIGTERM', (err) => {
          if (err && err.code !== 'ESRCH') {
            console.error(`[ProcessManager] Error sending SIGTERM to ${name}:`, err);
          }
        });
      } catch (e) {
        console.error(`[ProcessManager] Error sending graceful shutdown to ${name}:`, e);
        cleanup();
        return;
      }

      // 超时后强制终止
      const forceKillTimeout = setTimeout(() => {
        try {
          // 检查进程是否还在运行
          process.kill(0); // 发送信号 0 检查进程是否存在
          console.log(`[ProcessManager] Process ${name} did not terminate, forcing kill...`);
          treeKill(process.pid, 'SIGKILL', (err) => {
            if (err && err.code !== 'ESRCH') {
              console.error(`[ProcessManager] Error forcing kill on ${name}:`, err);
            }
            cleanup();
          });
        } catch (e) {
          // 进程已经退出
          cleanup();
        }
      }, timeout);

      // 如果进程已经退出，清理定时器
      if (process.killed) {
        clearTimeout(forceKillTimeout);
        cleanup();
      }
    });
  }

  // 关闭所有进程
  async killAll(timeout = 5000) {
    if (this.quitting) return;
    this.quitting = true;

    console.log(`[ProcessManager] Stopping all processes (${this.processes.size} processes)...`);
    
    const names = Array.from(this.processes.keys());
    await Promise.all(names.map(name => this.kill(name, timeout)));
    
    console.log('[ProcessManager] All processes stopped');
  }

  // 检查是否有进程在运行
  hasProcesses() {
    return this.processes.size > 0;
  }
}

const processManager = new ProcessManager();
let mainWindow = null;
const backendLogBuffer = [];
const MAX_LOGS = 2000;
let lastReadyLog = { message: '', ts: 0 };

function sendBackendLog(payload) {
  // 去重/限频：对“Server is ready”类信息做 3 秒限频，避免刷屏挤掉真实日志
  if (payload?.message) {
    const msg = payload.message;
    const now = Date.now();
    const isReadyMsg =
      msg.includes('Server is ready') ||
      msg.includes('Backend server is ready');
    if (isReadyMsg) {
      if (msg === lastReadyLog.message && now - lastReadyLog.ts < 3000) {
        return;
      }
      lastReadyLog = { message: msg, ts: now };
    }
  }

  // 写入缓冲区
  backendLogBuffer.push(payload);
  if (backendLogBuffer.length > MAX_LOGS) {
    backendLogBuffer.shift();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-log', payload);
  }
}

ipcMain.handle('backend-log-history', () => {
  return backendLogBuffer;
});

// 调试日志函数 - 同时输出到控制台和文件
function debugLog(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(message);
  
  // 同时写入日志文件
  try {
    const logDir = path.join(app.getPath('userData'), 'logs');
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    const logFile = path.join(logDir, 'backend-debug.log');
    fs.appendFileSync(logFile, logMessage, 'utf8');
  } catch (e) {
    // 忽略日志文件写入错误，避免影响主流程
    console.error(`[DebugLog] Failed to write to log file: ${e.message}`);
  }
}

// 获取项目根目录（包含 run_api.py 的目录）
function getProjectRoot() {
  debugLog('[Backend] getProjectRoot() called');
  debugLog(`[Backend] __dirname: ${__dirname}`);
  
  // 从 electron/ 目录向上到项目根目录
  // __dirname 指向 electron/ 目录，所以向上两级到项目根
  const projectRoot = path.resolve(__dirname, '..');
  debugLog(`[Backend] Resolved from __dirname: ${projectRoot}`);
  
  // 验证是否是项目根目录（检查是否存在 run_api.py）
  const runApiPath = path.join(projectRoot, 'run_api.py');
  debugLog(`[Backend] Checking run_api.py at: ${runApiPath}`);
  debugLog(`[Backend] File exists: ${fs.existsSync(runApiPath)}`);
  
  if (fs.existsSync(runApiPath)) {
    debugLog(`[Backend] Found run_api.py in project root: ${projectRoot}`);
    return projectRoot;
  }
  
  // 如果找不到，尝试使用 process.cwd()（开发时通常从项目根目录运行）
  const cwd = process.cwd();
  debugLog(`[Backend] process.cwd(): ${cwd}`);
  const cwdRunApiPath = path.join(cwd, 'run_api.py');
  debugLog(`[Backend] Checking run_api.py at: ${cwdRunApiPath}`);
  debugLog(`[Backend] File exists: ${fs.existsSync(cwdRunApiPath)}`);
  
  if (fs.existsSync(cwdRunApiPath)) {
    debugLog(`[Backend] Found run_api.py in cwd: ${cwd}`);
    return cwd;
  }
  
  // 如果都找不到，返回解析的路径（至少尝试）
  debugLog(`[Backend] WARNING: run_api.py not found in ${projectRoot} or ${cwd}`);
  debugLog(`[Backend] Returning projectRoot anyway: ${projectRoot}`);
  return projectRoot;
}

// 调试日志函数
function debugLog(message) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;
  console.log(message);
  
  // 同时写入日志文件
  try {
    const logDir = path.join(app.getPath('userData'), 'logs');
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    const logFile = path.join(logDir, 'backend-debug.log');
    fs.appendFileSync(logFile, logMessage, 'utf8');
  } catch (e) {
    // 忽略日志文件写入错误
  }
}

// 获取后端启动路径
function getBackendPath() {
  debugLog('=== getBackendPath() called ===');
  debugLog(`isDev: ${isDev}`);
  
  if (isDev) {
    // 开发环境：直接运行 Python 脚本
    debugLog('[Backend] Development mode: looking for run_api.py');
    const projectRoot = getProjectRoot();
    debugLog(`[Backend] Project root: ${projectRoot}`);
    debugLog(`[Backend] Project root exists: ${fs.existsSync(projectRoot)}`);
    
    const backendScript = path.join(projectRoot, 'run_api.py');
    debugLog(`[Backend] Looking for run_api.py at: ${backendScript}`);
    debugLog(`[Backend] run_api.py exists: ${fs.existsSync(backendScript)}`);
    
    // 验证文件是否存在
    if (!fs.existsSync(backendScript)) {
      debugLog(`[Backend] run_api.py not found at: ${backendScript}`);
      debugLog(`[Backend] Project root: ${projectRoot}`);
      
      // 尝试列出项目根目录的内容
      if (fs.existsSync(projectRoot)) {
        try {
          const contents = fs.readdirSync(projectRoot);
          debugLog(`[Backend] Project root contents: ${contents.join(', ')}`);
        } catch (e) {
          debugLog(`[Backend] Error reading project root: ${e.message}`);
        }
      }
      return null;
    }
    
    const absoluteScript = path.resolve(backendScript);
    debugLog(`[Backend] Found run_api.py: ${absoluteScript}`);
    debugLog(`[Backend] Using Python command: ${process.platform === 'win32' ? 'python' : 'python3'}`);
    
    return {
      command: process.platform === 'win32' ? 'python' : 'python3',
      args: [absoluteScript],
      cwd: projectRoot
    };
  } else {
    // 生产环境：使用打包的 Python 可执行文件
    // 在打包的应用中，extraResources 会被放在 resources 目录
    
    // 尝试多种方式获取 resources 路径
    let resourcesPath = null;
    
    // 调试信息：打印所有可能的路径
    debugLog(`[Backend] Debug info:`);
    debugLog(`  - app.isPackaged: ${app.isPackaged}`);
    debugLog(`  - process.resourcesPath: ${process.resourcesPath || '(undefined)'}`);
    debugLog(`  - process.execPath: ${process.execPath}`);
    debugLog(`  - __dirname: ${__dirname}`);
    debugLog(`  - process.cwd(): ${process.cwd()}`);
    
    // 方法1: process.resourcesPath (Electron 标准方式，在打包应用中可用)
    if (process.resourcesPath) {
      resourcesPath = process.resourcesPath;
      debugLog(`[Backend] Using process.resourcesPath: ${resourcesPath}`);
    }
    // 方法2: 从 app.getAppPath() 获取 (main.js 在 resources/app.asar 中)
    else if (app.isPackaged) {
      // 在打包应用中，__dirname 指向 resources/app.asar/main.js
      // 需要向上到 resources 目录
      const appPath = app.getAppPath();
      debugLog(`[Backend] app.getAppPath(): ${appPath}`);
      const appDir = path.dirname(appPath);
      debugLog(`[Backend] app directory: ${appDir}`);
      // app.asar 在 resources 目录下，所以 resourcesPath 就是 appDir
      resourcesPath = appDir;
      debugLog(`[Backend] Using app directory as resourcesPath: ${resourcesPath}`);
    }
    // 方法3: 从 exe 目录获取（适用于 unpacked 版本）
    else {
      // 从 exe 文件所在目录获取 resources
      const exePath = process.execPath;
      const exeDir = path.dirname(exePath);
      resourcesPath = path.join(exeDir, 'resources');
      debugLog(`[Backend] Using exe directory + resources: ${resourcesPath}`);
    }
    
    debugLog(`[Backend] Final resources path: ${resourcesPath}`);
    debugLog(`[Backend] Resources path exists: ${fs.existsSync(resourcesPath)}`);
    
    // 列出 resources 目录内容（用于调试）
    if (fs.existsSync(resourcesPath)) {
      try {
        const contents = fs.readdirSync(resourcesPath);
        debugLog(`[Backend] Resources directory contents: ${contents.join(', ')}`);
      } catch (e) {
        debugLog(`[Backend] Error reading resources directory: ${e.message}`);
      }
    }
    
    const backendExe = path.join(resourcesPath, 'backend', 'server.exe');
    debugLog(`[Backend] Looking for backend at: ${backendExe}`);
    debugLog(`[Backend] Backend path exists: ${fs.existsSync(backendExe)}`);
    
    // 如果找不到打包的 exe，尝试使用系统 Python（降级方案）
    if (fs.existsSync(backendExe)) {
      const absolutePath = path.resolve(backendExe);
      debugLog(`[Backend] Found backend executable: ${absolutePath}`);
      return {
        command: absolutePath,
        args: [],
        cwd: path.dirname(absolutePath)
      };
    } else {
      debugLog(`[Backend] Backend executable not found at: ${backendExe}`);
      debugLog(`[Backend] Attempted absolute path: ${path.resolve(backendExe)}`);
      
      // 尝试列出 backend 目录（如果存在）
      const backendDir = path.join(resourcesPath, 'backend');
      if (fs.existsSync(backendDir)) {
        try {
          const backendContents = fs.readdirSync(backendDir);
          debugLog(`[Backend] Backend directory contents: ${backendContents.join(', ')}`);
        } catch (e) {
          debugLog(`[Backend] Error reading backend directory: ${e.message}`);
        }
      } else {
        debugLog(`[Backend] Backend directory does not exist: ${backendDir}`);
      }
      
      // 降级：尝试使用系统 Python
      const backendScript = path.join(resourcesPath, 'backend', 'run_api.py');
      debugLog(`[Backend] Trying fallback Python script: ${backendScript}`);
      if (fs.existsSync(backendScript)) {
        debugLog(`[Backend] Found Python script, using system Python`);
        return {
          command: process.platform === 'win32' ? 'python' : 'python3',
          args: [backendScript],
          cwd: path.dirname(backendScript)
        };
      }
    }
    debugLog(`[Backend] All backend path resolution attempts failed`);
    return null;
  }
}

// 检查后端是否就绪
function waitForBackend(maxAttempts = 30, delay = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const checkHealth = () => {
      attempts++;
      const req = http.get(API_HEALTH_CHECK_URL, { timeout: 2000 }, (res) => {
        if (res.statusCode === 200) {
          console.log('[Backend] Server is ready!');
          resolve(true);
        } else {
          if (attempts < maxAttempts) {
            setTimeout(checkHealth, delay);
          } else {
            reject(new Error('Backend failed to start within timeout'));
          }
        }
      });
      
      req.on('error', () => {
        if (attempts < maxAttempts) {
          setTimeout(checkHealth, delay);
        } else {
          reject(new Error('Backend failed to start within timeout'));
        }
      });
      
      req.on('timeout', () => {
        req.destroy();
        if (attempts < maxAttempts) {
          setTimeout(checkHealth, delay);
        } else {
          reject(new Error('Backend health check timeout'));
        }
      });
    };
    
    checkHealth();
  });
}

// 启动后端服务器
function startBackend() {
  debugLog('=== startBackend() called ===');
  const backendConfig = getBackendPath();
  if (!backendConfig) {
    const errorMsg = '[Backend] Failed to find backend executable or script';
    console.error(errorMsg);
    debugLog(errorMsg);
    debugLog('=== startBackend() failed ===');
    
    // 获取日志文件路径
    const logPath = path.join(app.getPath('userData'), 'logs', 'backend-debug.log');
    debugLog(`Debug log saved to: ${logPath}`);
    
    return Promise.reject(new Error(`Backend not found. Check log file: ${logPath}`));
  }

  debugLog('[Backend] Starting backend server...');
  debugLog(`[Backend] Command: ${backendConfig.command}`);
  debugLog(`[Backend] Args: ${JSON.stringify(backendConfig.args)}`);
  debugLog(`[Backend] CWD: ${backendConfig.cwd}`);

  return new Promise((resolve, reject) => {
    try {
      // Windows: 先设置控制台代码页为 UTF-8
      if (process.platform === 'win32') {
        try {
          require('child_process').execSync('chcp 65001', { 
            shell: true,
            stdio: 'ignore'
          });
        } catch (e) {
          // 忽略错误，继续执行
        }
      }

      // 设置环境变量，确保中文正常显示
      const env = { ...process.env };
      if (process.platform === 'win32') {
        // Windows: 设置控制台代码页为 UTF-8
        env.PYTHONIOENCODING = 'utf-8';
        env.PYTHONUTF8 = '1';
        env.PYTHONLEGACYWINDOWSSTDIO = '0'; // 使用新的 UTF-8 模式
        // 确保控制台使用 UTF-8
        env.CHCP = '65001';
      } else {
        env.PYTHONIOENCODING = 'utf-8';
        env.PYTHONUTF8 = '1';
        env.LANG = 'en_US.UTF-8';
        env.LC_ALL = 'en_US.UTF-8';
      }

      const backendProcess = spawn(backendConfig.command, backendConfig.args, {
        cwd: backendConfig.cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: process.platform === 'win32',
        env: env
      });

      // 注册到进程管理器
      processManager.register('backend', backendProcess, 'backend');

      // 输出后端日志（可选，用于调试）
      // 设置 stdout/stderr 编码为 UTF-8
      if (backendProcess.stdout) {
        backendProcess.stdout.setEncoding('utf8');
      }
      if (backendProcess.stderr) {
        backendProcess.stderr.setEncoding('utf8');
      }

      const decodeOutput = (data) => {
        if (!data) return '';
        // 优先尝试 utf8；如果包含替换字符，再尝试 cp936（GBK）
        if (Buffer.isBuffer(data)) {
          let output = data.toString('utf8');
          if (output.includes('\uFFFD') || /��/.test(output)) {
            try {
              output = iconv.decode(data, 'cp936');
            } catch (e) {
              // 忽略，返回原始 utf8 输出
            }
          }
          return output;
        }
        return String(data);
      };

      // 处理 stdout 输出
      backendProcess.stdout.on('data', (data) => {
        try {
          const output = decodeOutput(data);
          console.log('[Backend]', output.trim());
          sendBackendLog({ level: 'info', message: output.trim() });
        } catch (err) {
          // 如果处理失败，至少输出原始数据
          console.log('[Backend]', String(data).trim());
          sendBackendLog({ level: 'info', message: String(data).trim() });
        }
      });

      // 处理 stderr 输出
      backendProcess.stderr.on('data', (data) => {
        try {
          const output = decodeOutput(data);
          console.error('[Backend]', output.trim());
          sendBackendLog({ level: 'error', message: output.trim() });
        } catch (err) {
          console.error('[Backend]', String(data).trim());
          sendBackendLog({ level: 'error', message: String(data).trim() });
        }
      });

      backendProcess.on('error', (error) => {
        console.error('[Backend] Failed to start:', error);
        processManager.kill('backend');
        reject(error);
      });

      backendProcess.on('exit', (code, signal) => {
        console.log(`[Backend] Process exited with code ${code} and signal ${signal}`);
        processManager.kill('backend');
        if (code !== 0 && code !== null) {
          // 非正常退出，可能需要通知用户
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('backend-error', { code, signal });
          }
        }
      });

      // 等待后端就绪
      waitForBackend()
        .then(() => {
          console.log('[Backend] Backend started successfully');
          resolve();
        })
        .catch((error) => {
          console.error('[Backend] Backend health check failed:', error);
          processManager.kill('backend');
          reject(error);
        });
    } catch (error) {
      console.error('[Backend] Exception starting backend:', error);
      reject(error);
    }
  });
}

// 启动前端开发服务器（仅在开发模式下）
function startFrontend() {
  if (!isDev) {
    return Promise.resolve();
  }

  // 检查前端 dev server 是否已经在运行
  return new Promise((resolve) => {
    const testReq = http.get('http://localhost:3000', { timeout: 1000 }, (res) => {
      // 前端服务器已经在运行
      console.log('[Frontend] Dev server already running on port 3000');
      resolve();
    });

    testReq.on('error', () => {
      // 前端服务器未运行，启动它
      console.log('[Frontend] Starting dev server...');
      const frontendDir = path.join(__dirname, '../frontend/web-chat');
      const fs = require('fs');
      
      if (!fs.existsSync(frontendDir)) {
        console.warn('[Frontend] Frontend directory not found, skipping dev server startup');
        resolve();
        return;
      }

      const frontendProcess = spawn('pnpm', ['dev'], {
        cwd: frontendDir,
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: process.platform === 'win32',
        env: { ...process.env }
      });

      // 注册到进程管理器
      processManager.register('frontend', frontendProcess, 'frontend');

      // 处理输出
      if (frontendProcess.stdout) {
        frontendProcess.stdout.setEncoding('utf8');
        frontendProcess.stdout.on('data', (data) => {
          const output = data.toString().trim();
          if (output) {
            console.log('[Frontend]', output);
          }
        });
      }

      if (frontendProcess.stderr) {
        frontendProcess.stderr.setEncoding('utf8');
        frontendProcess.stderr.on('data', (data) => {
          const output = data.toString().trim();
          if (output) {
            console.error('[Frontend]', output);
          }
        });
      }

      frontendProcess.on('error', (error) => {
        console.error('[Frontend] Failed to start:', error);
        processManager.kill('frontend');
        resolve(); // 不阻止应用启动
      });

      frontendProcess.on('exit', (code) => {
        if (code !== 0 && code !== null) {
          console.error(`[Frontend] Dev server exited with code ${code}`);
        }
        processManager.kill('frontend');
      });

      // 等待前端服务器就绪（最多等待 30 秒）
      let attempts = 0;
      const maxAttempts = 30;
      const checkReady = () => {
        attempts++;
        const req = http.get('http://localhost:3000', { timeout: 2000 }, (res) => {
          console.log('[Frontend] Dev server is ready!');
          resolve();
        });

        req.on('error', () => {
          if (attempts < maxAttempts) {
            setTimeout(checkReady, 1000);
          } else {
            console.warn('[Frontend] Dev server did not become ready, but continuing...');
            resolve(); // 不阻止应用启动
          }
        });
      };

      setTimeout(checkReady, 2000); // 等待 2 秒后开始检查
    });

    testReq.on('timeout', () => {
      testReq.destroy();
      // 超时也认为服务器未运行
      testReq.emit('error', new Error('Timeout'));
    });
  });
}

function createWindow() {
  const iconPath = getIconPath();
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    backgroundColor: '#0f172a',
    autoHideMenuBar: true,
    icon: iconPath, // 设置窗口图标
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  loadRenderer(mainWindow);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

async function loadRenderer(win) {
  if (isDev) {
    try {
      await win.loadURL(rendererDevURL);
      return;
    } catch (e) {
      console.warn('[Renderer] Dev server unreachable, fallback to static build:', e?.message || e);
    }
  }
  // Fallback to static build
  const prodPath = getRendererProdPath();
  debugLog(`[Renderer] Loading static build from: ${prodPath}`);
  
  // 在打包应用中，loadFile 可能无法直接访问 app.asar 内的文件
  // 尝试使用 loadURL 配合 file:// 协议
  try {
    if (app.isPackaged) {
      // 在打包应用中，尝试使用 loadFile（它应该能处理 app.asar 内的文件）
      // 如果失败，再尝试使用 loadURL
      try {
        await win.loadFile(prodPath);
        debugLog('[Renderer] Successfully loaded static build via loadFile');
      } catch (loadFileError) {
        debugLog(`[Renderer] loadFile failed, trying loadURL: ${loadFileError.message}`);
        // 使用 file:// 协议加载 app.asar 内的文件
        // 将 Windows 路径转换为 URL 格式
        let fileUrl = prodPath.replace(/\\/g, '/');
        // 确保路径以 / 开头（Windows 路径需要转换为 /C:/ 格式）
        if (!fileUrl.startsWith('/')) {
          fileUrl = '/' + fileUrl;
        }
        fileUrl = `file://${fileUrl}`;
        debugLog(`[Renderer] Using file:// URL: ${fileUrl}`);
        await win.loadURL(fileUrl);
        debugLog('[Renderer] Successfully loaded static build via loadURL');
      }
    } else {
      // 开发模式使用 loadFile
      await win.loadFile(prodPath);
      debugLog('[Renderer] Successfully loaded static build via loadFile');
    }
  } catch (e) {
    debugLog(`[Renderer] Failed to load static build: ${e.message}`);
    console.error('[Renderer] Failed to load static build:', e);
    
    // 尝试列出目录内容以帮助调试
    const dirPath = path.dirname(prodPath);
    try {
      if (fs.existsSync(dirPath)) {
        const contents = fs.readdirSync(dirPath);
        debugLog(`[Renderer] Directory contents: ${contents.join(', ')}`);
      } else {
        debugLog(`[Renderer] Directory does not exist: ${dirPath}`);
      }
    } catch (dirErr) {
      debugLog(`[Renderer] Error reading directory: ${dirErr.message}`);
    }
  }
}

app.whenReady().then(async () => {
  // Remove default application menu
  Menu.setApplicationMenu(null);

  // 在开发模式下启动前端 dev server
  if (isDev) {
    await startFrontend();
  }

  // 启动后端服务器
  try {
    await startBackend();
    // 后端启动成功后，创建窗口
    createWindow();
  } catch (error) {
    console.error('[App] Failed to start backend:', error);
    // 即使后端启动失败，也创建窗口（用户可能想手动启动后端）
    createWindow();
    // 可以显示错误提示给用户
    if (mainWindow) {
      mainWindow.webContents.once('did-finish-load', () => {
        mainWindow.webContents.executeJavaScript(`
          alert('后端服务器启动失败，请检查 Python 环境是否正确配置。\\n\\n错误: ${error.message}');
        `);
      });
    }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// 统一处理应用退出，确保所有进程优雅关闭
app.on('before-quit', async (event) => {
  if (processManager.quitting) return;
  
  // 阻止默认退出行为，等待所有进程关闭
  if (processManager.hasProcesses()) {
    event.preventDefault();
    console.log('[App] Quitting, stopping all processes...');
    await processManager.killAll(5000);
    console.log('[App] All processes stopped, exiting...');
    app.exit(0);
  }
});

