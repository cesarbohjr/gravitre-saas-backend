"""Read-only management API export; original SQL never goes to workflow logs."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

QUERY = 'select version,name,statements,created_by,rollback,idempotency_key from supabase_migrations.schema_migrations order by version'

def query(query_sql):
    token = os.environ['SUPABASE_ACCESS_TOKEN']
    ref = os.environ['RECOVERY_SOURCE_PROJECT_REF']
    if not ref.isalnum():
        raise ValueError('Invalid project reference')
    request = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{ref}/database/query',
        data=json.dumps({'query': query_sql, 'read_only': True}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        rows = json.load(response)
    return rows


def main():
    rows=query(QUERY)
    if not isinstance(rows, list) or not rows:
        raise ValueError('Expected nonempty migration history')
    target = Path(os.environ['RECOVERY_HISTORY_PATH'])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, indent=2) + '\n')
    target.chmod(0o600)
    for kind in ['inventory','columns']:
        metadata=query((Path(__file__).parent / (kind+'.sql')).read_text())
        if kind=='inventory': metadata=metadata[0]['inventory']
        target.with_name('production-'+kind+'.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps({'migration_count': len(rows), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}))

if __name__ == '__main__':
    main()
