#!/usr/bin/env python3
"""Bounded grep for lambda-closure variable capture (NameError class risk).

Pattern: lambda referencing loop/query variable defined outside (agent_platform_optimizer style).
Writes docs/delivery/lambda-closure-risk-grep.json
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "delivery" / "lambda-closure-risk-grep.json"

# Heuristic: lambda body references identifier also assigned in enclosing for/while scope.
PATTERNS = [
    re.compile(r"lambda\s+\w+\s*:\s*[^)]*\bquery\b", re.I),
    re.compile(r"lambda\s+\w+\s*:\s*_safe_query\s*\(", re.I),
    re.compile(r"key\s*=\s*lambda\s+\w+\s*:\s*_score_tool\s*\([^)]*\bquery\b", re.I),
    re.compile(r"min\s*\([^)]*key\s*=\s*lambda", re.I),
]

SCAN_DIRS = [
    ROOT / "backend" / "app",
    ROOT / "backend" / "tests",
]


def scan_file(path: Path) -> list[dict]:
    hits: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return hits
    for i, line in enumerate(lines, start=1):
        for pat in PATTERNS:
            if pat.search(line):
                hits.append(
                    {
                        "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "line": i,
                        "pattern": pat.pattern[:80],
                        "snippet": line.strip()[:200],
                    }
                )
                break
    return hits


def main() -> int:
    findings: list[dict] = []
    for base in SCAN_DIRS:
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            findings.extend(scan_file(path))

    known = {
        "backend/app/services/agent_platform_optimizer.py",
        "backend/app/services/b2b_handoff_service.py",
    }
    unexpected = [f for f in findings if f["file"] not in known]

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "finding_count": len(findings),
        "findings": findings,
        "known_sites": sorted(known),
        "unexpected_count": len(unexpected),
        "unexpected": unexpected,
        "verdict": "PASS — no new siblings" if not unexpected else f"REVIEW — {len(unexpected)} new hit(s)",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"verdict": report["verdict"], "finding_count": len(findings)}, indent=2))
    return 0 if not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
