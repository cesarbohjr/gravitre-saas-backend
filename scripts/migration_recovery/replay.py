"""Replay an exported migration history against a disposable local PostgreSQL only.

Never links to production, repairs remote metadata, or copies application rows.
The input is an off-database backup of schema_migrations, not a database dump.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import psycopg


def validate_history(rows):
    versions = [row['version'] for row in rows]
    if not versions or versions != sorted(versions) or len(set(versions)) != len(versions):
        raise ValueError('History must contain unique, ordered migration versions')
    for row in rows:
        if not isinstance(row.get('statements'), list) or not all(isinstance(s, str) for s in row['statements']):
            raise ValueError('Full original SQL statement arrays are required')
    return rows


def local_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {'postgres', 'postgresql'} or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Only loopback disposable database URLs are allowed')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history', required=True, type=Path)
    p.add_argument('--database-url', required=True, type=local_url)
    p.add_argument('--report', required=True, type=Path)
    args = p.parse_args()
    raw = args.history.read_bytes()
    rows = validate_history(json.loads(raw))
    report = {'history_sha256': hashlib.sha256(raw).hexdigest(), 'migration_count': len(rows),
              'applied': [], 'passed': False, 'source': 'input SQL arrays; no runtime compatibility rewrites'}
    try:
        with psycopg.connect(args.database_url, autocommit=True) as conn:
            # Refuse a database that already contains Gravitre application tables.
            if conn.execute("select to_regclass('public.organizations')").fetchone()[0]:
                raise ValueError('Target must be a fresh disposable database')
            for row in rows:
                index = None
                try:
                    with conn.transaction():
                        for index, sql in enumerate(row['statements']):
                            conn.execute(sql, prepare=False)
                    report['applied'].append(row['version'])
                except psycopg.Error as exc:
                    report['failure'] = {'version': row['version'], 'name': row['name'],
                                         'statement_number': index + 1, 'sqlstate': exc.sqlstate,
                                         'message': exc.diag.message_primary, 'detail': exc.diag.message_detail,
                                         'hint': exc.diag.message_hint,
                                         'statement_sha256': hashlib.sha256(row['statements'][index].encode()).hexdigest()}
                    raise
            report['passed'] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'applied'}, indent=2))


if __name__ == '__main__':
    main()
