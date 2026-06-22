#!/usr/bin/env python3
"""Run pip-audit for backend dependencies (STA-278).

Audits requirements-audit.txt (core) on all platforms. On Linux, also audits
requirements-extras-data.txt (snowflake connector with prebuilt wheels).
Uses Python 3.12 when available (py -3.12 / python3.12).
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
AUDIT_CORE = BACKEND / "requirements-audit.txt"
AUDIT_EXTRAS = BACKEND / "requirements-extras-data.txt"


def _python_for_audit() -> list[str]:
    if sys.version_info[:2] == (3, 12):
        return [sys.executable]
    candidates: list[list[str]] = []
    if shutil.which("py"):
        candidates.append(["py", "-3.12"])
    if shutil.which("python3.12"):
        candidates.append(["python3.12"])
    if shutil.which("python3"):
        candidates.append(["python3"])
    for cmd in candidates:
        try:
            subprocess.run(
                [*cmd, "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        return cmd
    return [sys.executable]


def _run_pip_audit(python_cmd: list[str], requirements: Path) -> int:
    subprocess.run(
        [*python_cmd, "-m", "pip", "install", "--upgrade", "pip", "pip-audit"],
        check=True,
    )
    print(f"pip-audit: {requirements.relative_to(ROOT)}")
    result = subprocess.run(
        [*python_cmd, "-m", "pip_audit", "-r", str(requirements)],
    )
    return int(result.returncode)


def main() -> int:
    python_cmd = _python_for_audit()
    print(f"Using Python: {' '.join(python_cmd)}")

    exit_code = _run_pip_audit(python_cmd, AUDIT_CORE)
    if exit_code != 0:
        return exit_code

    if platform.system().lower() == "linux" and AUDIT_EXTRAS.is_file():
        extras_code = _run_pip_audit(python_cmd, AUDIT_EXTRAS)
        if extras_code != 0:
            return extras_code

    print("pip-audit: all targets passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
