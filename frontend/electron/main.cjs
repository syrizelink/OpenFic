/**
 * OpenFic Electron 主进程。
 *
 * 职责：spawn PyInstaller 后端子进程 → 轮询健康检查 → 加载窗口。
 * 退出时确保后端子进程被终止（含异常路径），符合项目生命周期约束。
 */

const { app, BrowserWindow, shell, dialog } = require("electron");
const { spawn } = require("node:child_process");
const { openSync, writeSync } = require("node:fs");
const { open } = require("node:fs/promises");
const path = require("node:path");
const net = require("node:net");
const http = require("node:http");

let backendProcess = null;
let mainWindow = null;
let isQuitting = false;
let backendLogPath = null;
let failureReported = false;

const DEV_SERVER_URL = process.env.OPENFIC_ELECTRON_DEV_URL || null;
const HEALTH_TIMEOUT_MS = 60000;

function getBackendExePath() {
  const exeName =
    process.platform === "win32" ? "openfic-server.exe" : "openfic-server";
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "openfic-server", exeName);
  }
  return path.join(__dirname, "..", "..", "backend", "dist", "openfic-server", exeName);
}

async function reportBackendFailure(reason) {
  if (failureReported || isQuitting) return;
  failureReported = true;
  let detail = reason || "后端服务异常退出。";
  if (backendLogPath) {
    let tail = "";
    try {
      const fh = await open(backendLogPath, "r");
      const stat = await fh.stat();
      const size = Math.min(stat.size, 4096);
      if (size > 0) {
        const buf = Buffer.alloc(size);
        await fh.read(buf, 0, size, Math.max(0, stat.size - size));
        tail = buf.toString("utf-8");
      }
      await fh.close();
    } catch {
      // 日志读取失败时忽略，仍提示路径
    }
    detail += `\n\n后端日志路径：${backendLogPath}`;
    if (tail.trim()) {
      detail += `\n\n日志末尾：\n${tail.trimEnd()}`;
    }
  }
  dialog.showErrorBox("OpenFic 启动失败", detail);
  app.quit();
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

function waitForBackend(port) {
  const start = Date.now();
  const url = `http://127.0.0.1:${port}/api/v1/health`;
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(url, (res) => {
        res.resume();
        if (res.statusCode === 200) {
          resolve();
        } else if (Date.now() - start > HEALTH_TIMEOUT_MS) {
          reject(new Error("backend health check timeout"));
        } else {
          setTimeout(check, 500);
        }
      });
      req.on("error", () => {
        if (Date.now() - start > HEALTH_TIMEOUT_MS) {
          reject(new Error("backend health check timeout"));
        } else {
          setTimeout(check, 500);
        }
      });
    };
    check();
  });
}

function startBackend(port) {
  const exe = getBackendExePath();
  const dataDir = app.getPath("userData");
  backendLogPath = path.join(dataDir, "openfic-backend.log");
  const logFd = openSync(backendLogPath, "w");
  backendProcess = spawn(exe, [], {
    cwd: dataDir,
    env: {
      ...process.env,
      OPENFIC_PORT: String(port),
      OPENFIC_HOST: "127.0.0.1",
      OPENFIC_DATA_DIR: dataDir,
    },
    windowsHide: true,
    stdio: ["ignore", logFd, logFd],
  });
  backendProcess.on("exit", () => {
    backendProcess = null;
    if (!isQuitting) {
      reportBackendFailure("后端服务已退出。");
    }
  });
}

function killBackend() {
  if (!backendProcess) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/F", "/T", "/PID", String(backendProcess.pid)], {
      windowsHide: true,
      stdio: "ignore",
    });
  } else {
    backendProcess.kill("SIGTERM");
  }
  backendProcess = null;
}

async function createWindow(targetUrl) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      contextIsolation: true,
    },
  });
  await mainWindow.loadURL(targetUrl);
  mainWindow.show();
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    try {
      if (DEV_SERVER_URL) {
        await createWindow(DEV_SERVER_URL);
        return;
      }
      const port = await findFreePort();
      startBackend(port);
      await waitForBackend(port);
      await createWindow(`http://127.0.0.1:${port}`);
    } catch (err) {
      await reportBackendFailure(String(err));
    }
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  app.on("before-quit", () => {
    isQuitting = true;
    killBackend();
  });

  process.on("exit", () => killBackend());
  process.on("SIGINT", () => {
    killBackend();
    process.exit(0);
  });
  process.on("SIGTERM", () => {
    killBackend();
    process.exit(0);
  });
}
