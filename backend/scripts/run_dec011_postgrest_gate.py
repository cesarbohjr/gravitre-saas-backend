"""Mandatory DEC-011 persisted reader/consumer gate, independent of DEC-008."""
import os

from run_dec008_postgrest_gate import run_gate


if __name__ == "__main__":
    raise SystemExit(run_gate(
        finding="DEC-011", test_file="tests/test_dec011_department_memory_postgrest.py",
        count=6, output_name="dec011-postgrest-evidence.json",
        expected_sha_env="DEC011_EXPECTED_SHA", strict_checkout=True,
        expected_pg_version=os.environ.get("DEC011_EXPECTED_PG_VERSION", "18.7"),
    ))
