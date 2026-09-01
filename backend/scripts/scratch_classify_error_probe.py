"""What does _classify_error do with real transport faults today?"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
for p in (ROOT / "backend" / ".env", ROOT / ".env"):
    if p.is_file():
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue

from app.services.tool_service import _classify_error  # noqa: E402

CASES = [
    httpx.RemoteProtocolError(
        "<ConnectionTerminated error_code:1, last_stream_id:107, additional_data:None>"
    ),
    OSError(11, "Resource temporarily unavailable"),
    httpx.ConnectTimeout("timed out"),
    httpx.ReadTimeout("read timed out"),
    httpx.ConnectError("[Errno 111] Connection refused"),
    ConnectionResetError("Connection reset by peer"),
    ValueError("name is required"),
    KeyError("dealname"),
]


def main() -> int:
    for exc in CASES:
        err = _classify_error(exc)
        print(f"  {type(exc).__name__:24} code={err.code:22} msg={str(exc)[:50]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
