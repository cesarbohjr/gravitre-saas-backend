"""DIAGNOSIS ONLY: pull version/name/created_by for migration drift window."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ONLY = {
    "20260725085714",
    "20260725234024",
    "20260731001645",
    "20260801060750",
    "20260802223452",
    "20260804021749",
    "20260808065607",
    "20260808085000",
    "20260808204958",
    "20260809044816",
    "20260809085843",
}
LOCAL_ONLY = {
    "20260725120000",
    "20260725180000",
    "20260725190000",
    "20260726120000",
    "20260730120000",
    "20260801120000",
    "20260802120000",
    "20260804020000",
    "20260805140000",
    "20260805210000",
    "20260805220000",
    "20260805221000",
    "20260807140000",
    "20260808010000",
    "20260808120000",
    "20260808140000",
    "20260809010000",
    "20260809120000",
    "20260811120000",
}


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
    r = subprocess.run(
        "npx --yes supabase db query --linked -f docs/delivery/_diag_schema_migrations_names.sql -o json",
        shell=True,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = r.stdout or ""
    (ROOT / "docs" / "delivery" / "_remote_mig_names.json").write_text(raw, encoding="utf-8")
    data = json.loads(raw)
    rows = data.get("rows") or []
    by = {str(row.get("version")): row for row in rows}

    # Map local files by snake name stem
    local_files = {}
    for p in (ROOT / "supabase" / "migrations").glob("*.sql"):
        ver = p.name.split("_", 1)[0]
        name = p.stem.split("_", 1)[1] if "_" in p.stem else p.stem
        local_files.setdefault(ver, []).append({"file": p.name, "name_stem": name})

    mapping = []
    for v in sorted(REMOTE_ONLY):
        row = by.get(v, {})
        rname = row.get("name") or ""
        # find local file with matching stem / substring
        candidates = []
        for ver, files in local_files.items():
            for f in files:
                stem = f["name_stem"]
                if rname and (rname == stem or rname.replace("_columns", "") in stem or stem in rname):
                    candidates.append({"local_version": ver, **f})
        mapping.append(
            {
                "remote_version": v,
                "remote_name": rname,
                "created_by": row.get("created_by"),
                "local_candidates": candidates,
                "on_local_filesystem_as_same_version": v in local_files,
            }
        )

    report = {
        "remote_count_from_20260725": len(rows),
        "remote_only_mapped": mapping,
        "local_only_versions_present_on_remote": {
            v: {"present": v in by, "name": (by.get(v) or {}).get("name")} for v in sorted(LOCAL_ONLY)
        },
        "all_recent": [
            {"version": r.get("version"), "name": r.get("name"), "created_by": r.get("created_by")}
            for r in rows
        ],
    }
    out_path = ROOT / "docs" / "delivery" / "supabase-migration-history-drift-mapping.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2)[:12000])


if __name__ == "__main__":
    main()
