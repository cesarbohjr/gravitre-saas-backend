"""DIAGNOSIS ONLY: read remote schema_migrations rows (no repair)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_bytes().decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> None:
    env = os.environ.copy()
    for p in (ROOT / "backend" / ".env", ROOT / "backend" / ".env.operator.local"):
        env.update(load_env(p))

    queries = {
        "columns": """
select column_name, data_type
from information_schema.columns
where table_schema = 'supabase_migrations' and table_name = 'schema_migrations'
order by ordinal_position;
""",
        "recent_from_20260725": """
select version, name
from supabase_migrations.schema_migrations
where version >= '20260725'
order by version;
""",
        "count_all": """
select count(*)::int as n from supabase_migrations.schema_migrations;
""",
    }
    out: dict[str, object] = {}
    for label, sql in queries.items():
        r = subprocess.run(
            f'npx --yes supabase db query --linked "{sql.strip()}"',
            shell=True,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
        )
        out[label] = {
            "exit": r.returncode,
            "stdout": r.stdout,
            "stderr": r.stderr[-2000:] if r.stderr else "",
        }
        print("===", label, "exit", r.returncode, "===")
        print((r.stdout or "")[:8000])
        print((r.stderr or "")[-1200:])

    (ROOT / "docs" / "delivery" / "_remote_schema_migrations_query.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
