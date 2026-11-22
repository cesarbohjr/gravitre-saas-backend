"""Required offline DEC-008 gate: real PostgREST, exact checkout and zero skips."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def require_complete_junit(path: Path) -> int:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    if len(cases) != 20 or any(case.find(tag) is not None for case in cases
                               for tag in ("skipped", "failure", "error")):
        raise ValueError("DEC-008 requires all 20 real-PostgREST cases, zero skips/failures/errors")
    return len(cases)


def main() -> int:
    evidence = {"schema_version": 1, "status": "FAILED", "certifies_whole_finding": False,
                "external_project_used": False, "provider_acceptance": "NOT_RUN"}
    output = Path("dec008-postgrest-evidence.json")
    try:
        from tests.db.pg_harness import PG_BIN

        binary = os.environ.get("GRAVITRE_POSTGREST_BIN")
        if PG_BIN is None or not binary or not Path(binary).is_file():
            raise ValueError("Real PostgreSQL/PostgREST unavailable; skipped tests cannot pass this gate")
        version = subprocess.check_output([binary,"--version"],text=True).strip()
        if version != "PostgREST 16.6":
            raise ValueError("Unexpected PostgREST version; expected pinned 16.6")
        sha = subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        expected = os.environ.get("DEC008_EXPECTED_SHA",sha)
        if sha != expected:
            raise ValueError("DEC-008 checkout does not match the exact expected PR head")
        evidence.update(git_sha=sha,postgrest_version=version,
                        postgres_version=subprocess.check_output([str(PG_BIN/"postgres"),"--version"],text=True).strip())
        with tempfile.TemporaryDirectory(prefix="dec008-junit-") as directory:
            report = Path(directory)/"results.xml"
            result = subprocess.run([sys.executable,"-m","pytest","tests/test_audit_reader_postgrest.py",
                                     "-q","--tb=short",f"--junitxml={report}"])
            if result.returncode != 0:
                raise ValueError("Real-PostgREST pytest execution failed")
            count = require_complete_junit(report)
        evidence.update(status="PASS",tests=count,skipped=0)
        return 0
    except Exception as exc:
        evidence.update(failure_class=type(exc).__name__,failure_reason=str(exc))
        return 1
    finally:
        output.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
        print(json.dumps(evidence,sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
