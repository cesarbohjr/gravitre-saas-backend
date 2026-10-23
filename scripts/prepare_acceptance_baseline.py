#!/usr/bin/env python3
"""Validate a CI-exported, data-free Gravitre schema baseline; never execute SQL."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys


def prepare(folder: Path) -> dict:
    baselines = list(folder.rglob("production-schema-baseline.sql"))
    checksums = list(folder.rglob("production-schema-baseline.sha256"))
    if len(baselines) != 1 or len(checksums) != 1:
        raise ValueError("Expected exactly one schema baseline and one SHA256 manifest")
    baseline, checksum = baselines[0], checksums[0]
    data = baseline.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    expected = checksum.read_text().split()[0]
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or digest != expected:
        raise ValueError("Baseline SHA256 does not match CI manifest")
    if not (50_000 <= len(data) <= 50_000_000):
        raise ValueError("Unexpected schema-baseline size")
    sql = data.decode("utf-8")
    if ("CREATE TABLE " not in sql and "CREATE TABLE IF NOT EXISTS" not in sql):
        raise ValueError("Baseline contains no application table definitions")
    # Reject common data-bearing constructs. CREATE FUNCTION bodies may legitimately
    # contain INSERT/UPDATE statements, so do not blindly reject those tokens.
    for pattern in (
        r"(?im)^\s*COPY\s+(?:public\.|auth\.)",
        r"(?im)^\s*INSERT\s+INTO\s+auth\.users",
        r"(?im)^\s*CREATE\s+DATABASE\b",
        r"(?im)^\s*\\connect\b",
    ):
        if re.search(pattern, sql):
            raise ValueError("Found disallowed data-bearing or cluster SQL in baseline")
    return {
        "status": "VERIFIED_DATA_FREE_BASELINE",
        "sha256": digest,
        "size_bytes": len(data),
        "source": "migration-history-replay CI artifact",
        "remote_write_performed": False,
    }


def main() -> int:
    folder = Path(sys.argv[1])
    report_path = folder / "readiness-report.json"
    try:
        report = prepare(folder)
    except (OSError, UnicodeError, ValueError) as exc:
        report = {"status": "BLOCKED", "reason": str(exc), "remote_write_performed": False}
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
        return 2
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
