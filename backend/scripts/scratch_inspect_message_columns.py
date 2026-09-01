"""What does conversation_messages actually persist per assistant turn?

The terminal `model` label is passed to the SSE complete event, but that is not
proof it reaches storage. Read a real row before building any analysis on it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402


def main() -> int:
    env = load_env()
    from supabase import create_client

    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    rows = (
        sb.table("conversation_messages")
        .select("*")
        .eq("role", "assistant")
        .order("created_at", desc=True)
        .limit(3)
        .execute()
        .data
        or []
    )
    if not rows:
        print("no assistant messages found")
        return 1
    print("=== columns ===")
    for k in sorted(rows[0].keys()):
        print(f"  {k}")
    print("\n=== newest row (truncated) ===")
    print(json.dumps(rows[0], indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
