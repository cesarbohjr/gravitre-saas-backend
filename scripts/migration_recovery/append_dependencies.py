"""Append application triggers on managed tables omitted by public-only schema dumps."""
import json
from pathlib import Path
import sys
from reconcile import q
source,dump=map(Path,sys.argv[1:])
metadata=json.loads(source.read_text())
prefix='CREATE SCHEMA IF NOT EXISTS extensions;\n'
for extension in metadata.get('extensions') or []:
    prefix+='CREATE EXTENSION IF NOT EXISTS '+q(extension['name'])+' WITH SCHEMA '+q(extension['schema'])+" VERSION '"+extension['version'].replace("'","''")+"';\n"
prefix+='\n'.join([
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon,authenticated,service_role;',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon,authenticated,service_role;',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC,anon,authenticated,service_role;',
])+'\n'
dump.write_text(prefix+dump.read_text())
with dump.open('a') as out:
    out.write('\nSET search_path=public,extensions;\n')
    for trigger in metadata['triggers']:
        if trigger.get('schema','public')=='public': continue
        out.write(f'DROP TRIGGER IF EXISTS {q(trigger["name"])} ON {q(trigger["schema"])}.{q(trigger["table"])};\n')
        out.write(trigger['definition'].rstrip().rstrip(';')+';\n')
