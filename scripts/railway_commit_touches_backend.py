#!/usr/bin/env python3
"""Return whether a git revision range touches backend/ (Railway service root)."""
from __future__ import annotations

import argparse
import subprocess
import sys


def commit_range_touches_backend(base: str, head: str) -> tuple[bool, list[str]]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git diff failed").strip())
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    backend_paths = [path for path in paths if path.startswith("backend/")]
    return bool(backend_paths), backend_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD~1", help="Base ref (default HEAD~1)")
    parser.add_argument("--head", default="HEAD", help="Head ref (default HEAD)")
    args = parser.parse_args()

    try:
        changed, paths = commit_range_touches_backend(args.base, args.head)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if changed:
        print(f"backend_changed=true count={len(paths)}")
        for path in paths[:20]:
            print(path)
        if len(paths) > 20:
            print(f"... and {len(paths) - 20} more")
    else:
        print("backend_changed=false")
    return 0 if changed else 1


if __name__ == "__main__":
    raise SystemExit(main())
