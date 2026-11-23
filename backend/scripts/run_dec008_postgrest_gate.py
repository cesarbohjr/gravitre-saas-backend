"""Required offline DEC-008 gate: real PostgREST, exact checkout and zero skips."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def require_complete_junit(path: Path, *, count: int = 20, finding: str = "DEC-008") -> int:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    if len(cases) != count or any(case.find(tag) is not None for case in cases
                               for tag in ("skipped", "failure", "error")):
        raise ValueError(f"{finding} requires all {count} real-PostgREST cases, zero skips/failures/errors")
    return len(cases)


def run_gate(*, finding: str, test_file: str, count: int, output_name: str,
             expected_sha_env: str, expected_pg_version: str | None = None,
             strict_checkout: bool = False) -> int:
    evidence = {"schema_version": 1, "status": "FAILED", "certifies_whole_finding": False,
                "external_project_used": False, "provider_acceptance": "NOT_RUN"}
    output = Path(output_name)
    try:
        from tests.db.pg_harness import PG_BIN

        binary = os.environ.get("GRAVITRE_POSTGREST_BIN")
        if PG_BIN is None or not binary or not Path(binary).is_file():
            raise ValueError("Real PostgreSQL/PostgREST unavailable; skipped tests cannot pass this gate")
        version = subprocess.check_output([binary,"--version"],text=True).strip()
        if version != "PostgREST 16.6":
            raise ValueError("Unexpected PostgREST version; expected pinned 16.6")
        sha = subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        expected = os.environ.get(expected_sha_env, "" if strict_checkout else sha)
        if strict_checkout and not re.fullmatch(r"[0-9a-f]{40}", expected):
            raise ValueError(f"{finding} requires an explicit exact expected SHA")
        if sha != expected:
            raise ValueError(f"{finding} checkout does not match the exact expected PR head")
        if strict_checkout:
            subprocess.check_call(["git", "diff", "--quiet", "HEAD", "--"])
        pg_version = subprocess.check_output([str(PG_BIN/"postgres"),"--version"],text=True).strip()
        if expected_pg_version is not None:
            match = re.match(r"^postgres \(PostgreSQL\) (\d+\.\d+)(?:\s|$)", pg_version)
            if match is None or match.group(1) != expected_pg_version:
                raise ValueError(f"Unexpected PostgreSQL version; expected pinned {expected_pg_version}")
        evidence.update(git_sha=sha,postgrest_version=version,
                        postgres_version=pg_version)
        if expected_pg_version is not None:
            evidence["expected_postgres_version"] = expected_pg_version
        with tempfile.TemporaryDirectory(prefix=f"{finding.lower()}-junit-") as directory:
            report = Path(directory)/"results.xml"
            result = subprocess.run([sys.executable,"-m","pytest",test_file,
                                     "-q","--tb=short",f"--junitxml={report}"])
            if result.returncode != 0:
                raise ValueError("Real-PostgREST pytest execution failed")
            passed = require_complete_junit(report, count=count, finding=finding)
        evidence.update(status="PASS",tests=passed,skipped=0)
        return 0
    except Exception as exc:
        evidence.update(failure_class=type(exc).__name__,failure_reason=str(exc))
        return 1
    finally:
        output.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
        print(json.dumps(evidence,sort_keys=True))


def main() -> int:
    # Preserve the independent DEC-008 command, file selection and 20-case gate.
    return run_gate(finding="DEC-008", test_file="tests/test_audit_reader_postgrest.py",
                    count=20, output_name="dec008-postgrest-evidence.json",
                    expected_sha_env="DEC008_EXPECTED_SHA")


if __name__ == "__main__":
    raise SystemExit(main())
