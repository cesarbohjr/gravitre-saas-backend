#!/usr/bin/env python3
"""Print UNIFIED_TURN_* / GIT_SHA from railway variables --json output."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vars.json")
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    if not isinstance(data, dict):
        print(f"unexpected vars payload type={type(data)}")
        return 1
    for key in ("UNIFIED_TURN_LIVE_ENABLED", "UNIFIED_TURN_SHADOW_ENABLED", "GIT_SHA"):
        print(f"{key}={data.get(key)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
