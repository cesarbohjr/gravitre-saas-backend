"""Prove atomic metadata replacement on disposable loopback PostgreSQL only.

This is a PostgreSQL transaction, NOT a Supabase squash/repair side effect.
It is intentionally incapable of accepting a production database hostname.
"""
import argparse
import hashlib
import json
from pathlib import Path

import psycopg
from replay import local_url, validate_history


def adopt(conn, *, original, version: str, baseline: str):
    if not version.isdigit() or len(version) != 14 or not baseline.strip():
        raise ValueError("A version and nonempty verified baseline SQL are required")
    expected = [(row["version"], row["name"], row["statements"]) for row in validate_history(original)]
    with conn.transaction():
        conn.execute("LOCK TABLE supabase_migrations.schema_migrations IN ACCESS EXCLUSIVE MODE")
        current = conn.execute("SELECT version,name,statements FROM supabase_migrations.schema_migrations ORDER BY version").fetchall()
        if current != expected:
            raise ValueError("Migration metadata drifted; refusing replacement")
        conn.execute("DELETE FROM supabase_migrations.schema_migrations")
        # The drill's CHECK constraint rejects this insert deliberately on the
        # first run; the transaction must restore every original SQL array.
        conn.execute("INSERT INTO supabase_migrations.schema_migrations(version,name,statements) VALUES (%s,%s,%s)",
                     (version, "production_replay_baseline", [baseline]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database_url", type=local_url)
    parser.add_argument("history", type=Path)
    parser.add_argument("version")
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    baseline = args.baseline.read_text()
    with psycopg.connect(args.database_url) as conn:
        adopt(conn, original=json.loads(args.history.read_text()), version=args.version, baseline=baseline)
    print(json.dumps({"operation": "atomic_loopback_metadata_replacement", "production_mutated": False,
                      "baseline_sha256": hashlib.sha256(baseline.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
