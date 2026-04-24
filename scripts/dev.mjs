import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import process from "node:process";

const root = process.cwd();
const backendCwd = join(root, "backend");
const webCwd = join(root, "apps", "web");
const isWin = process.platform === "win32";

const venvPython = join(
  backendCwd,
  ".venv",
  isWin ? "Scripts" : "bin",
  isWin ? "python.exe" : "python"
);
const pythonCmd = existsSync(venvPython) ? venvPython : "python";

const backend = spawn(
  pythonCmd,
  ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
  { cwd: backendCwd, stdio: "inherit", shell: false }
);

const web = spawn("pnpm", ["dev"], { cwd: webCwd, stdio: "inherit", shell: true });

const shutdown = (signal) => {
  backend.kill(signal);
  web.kill(signal);
};

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

const exitAll = (code) => {
  if (code && code !== 0) {
    process.exitCode = code;
  }
  shutdown("SIGTERM");
};

backend.on("exit", exitAll);
web.on("exit", exitAll);
