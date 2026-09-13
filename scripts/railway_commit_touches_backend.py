#!/usr/bin/env python3
"""Return whether a git revision range touches a Railway-deployed backend path.

IMPORTANT (2026-09-13): this used to treat ANY path under backend/ as a reason
to run the Railway deploy-verification gate (wait for /health git_sha to reach
tip, force-redeploy if stale). But backend/railway.toml's own `watchPatterns`
only rebuilds the running image for app/**, requirements*.txt, Dockerfile,
railway.toml, pyproject.toml, and .railway-deploy-stamp — NOT backend/scripts/**
or backend/tests/**. A script- or test-only commit under backend/ therefore
triggered the gate, which then waited the full timeout for a redeploy that
Railway was never going to do, and failed the job (see e.g. run 34728926180
for commit 9aacb559, a scripts-only change). Scope this to the same globs
Railway itself watches so the gate only runs when something could actually
change what's live.
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys

# Mirrors backend/railway.toml's watchPatterns (repo-root-relative half).
# Keep in sync with that file — it is the actual source of truth for what
# Railway rebuilds on.
DEPLOY_RELEVANT_GLOBS: tuple[str, ...] = (
    "backend/app/**",
    "backend/requirements*.txt",
    "backend/Dockerfile",
    "backend/railway.toml",
    "backend/pyproject.toml",
    "backend/.railway-deploy-stamp",
    # The gate workflow file itself and this detector script — changes to the
    # deploy-verification machinery should always re-run the gate.
    ".github/workflows/railway-backend-production.yml",
    "scripts/railway_commit_touches_backend.py",
    "scripts/railway_prod_deploy.py",
)


def _is_deploy_relevant(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in DEPLOY_RELEVANT_GLOBS)


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
    backend_paths = [path for path in paths if _is_deploy_relevant(path)]
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
