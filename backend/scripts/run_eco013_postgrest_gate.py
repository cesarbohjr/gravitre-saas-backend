"""Mandatory ECO-013/DEC-005 conversation writer gate; separate from reader gates."""
import os

from run_dec008_postgrest_gate import run_gate


if __name__ == "__main__":
    raise SystemExit(run_gate(
        finding="ECO-013", test_file="tests/test_eco013_plan_authority_postgrest.py",
        count=8, output_name="eco013-postgrest-evidence.json",
        expected_sha_env="ECO013_EXPECTED_SHA", strict_checkout=True,
        expected_pg_version=os.environ.get("ECO013_EXPECTED_PG_VERSION", "18.7"),
    ))
