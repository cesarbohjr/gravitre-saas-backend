"""Restore all original migration metadata in an isolated scratch schema and compare."""
import json
from pathlib import Path
import sys
import psycopg
from psycopg.types.json import Jsonb
from replay import local_url, validate_history

url=local_url(sys.argv[1]); rows=validate_history(json.loads(Path(sys.argv[2]).read_text()))
with psycopg.connect(url) as conn:
    conn.execute('CREATE SCHEMA recovery_rollback')
    conn.execute('CREATE TABLE recovery_rollback.history(version text primary key, metadata jsonb not null)')
    for row in rows:
        conn.execute('insert into recovery_rollback.history values (%s,%s)',(row['version'],Jsonb(row)))
    restored=[r[0] for r in conn.execute('select metadata from recovery_rollback.history order by version')]
    assert restored==rows, 'Original statement arrays or metadata did not round-trip'
    conn.execute('DROP SCHEMA recovery_rollback CASCADE')
Path(sys.argv[3]).write_text(json.dumps({'passed':True,'restored_records':len(rows),'original_statement_arrays_preserved':True,'scope':'isolated rollback backup restoration; no production writes'},indent=2)+'\n')
