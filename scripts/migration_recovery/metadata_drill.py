"""Exercise the supported squash transaction against loopback metadata only."""
import json
from pathlib import Path
import sys
import psycopg
from psycopg import sql
from replay import local_url

mode,url,history_path,version,report_path=sys.argv[1:]
url=local_url(url); original=json.loads(Path(history_path).read_text())
expected=[(r['version'],r['name'],r['statements']) for r in original]
with psycopg.connect(url) as conn:
    if mode=='prepare':
        assert conn.execute('select count(*) from supabase_migrations.schema_migrations').fetchone()[0]==0
        for row in expected:
            conn.execute('insert into supabase_migrations.schema_migrations(version,name,statements) values (%s,%s,%s)',row)
        conn.execute(sql.SQL('alter table supabase_migrations.schema_migrations add constraint recovery_reject_baseline check(version<>{})').format(sql.Literal(version)))
    elif mode=='check-rollback':
        restored=conn.execute('select version,name,statements from supabase_migrations.schema_migrations order by version').fetchall()
        assert restored==expected,'CLI failed to roll back original migration history after rejected baseline INSERT'
        conn.execute('alter table supabase_migrations.schema_migrations drop constraint recovery_reject_baseline')
    elif mode=='check-success':
        rows=conn.execute('select version,name,statements from supabase_migrations.schema_migrations').fetchall()
        assert len(rows)==1 and rows[0][0]==version and rows[0][2],rows
        Path(report_path).write_text(json.dumps({'passed':True,'original_record_count':len(original),'baselined_record_count':1,'baseline_version':version,'forced_insert_failure_preserved_original_sql_arrays':True,'supported_command':'supabase migration squash --db-url (loopback)','production_mutated':False},indent=2)+'\n')
    else:raise ValueError(mode)
