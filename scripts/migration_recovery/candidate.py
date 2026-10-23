"""Build an isolated replay candidate; never edits production or original backup."""
import copy
import json
from pathlib import Path
import sys


def build(original, root):
    rows = copy.deepcopy(original)
    by_version = {row['version']: row for row in rows}
    def prelude(version, source, start, end):
        sql = (root / source).read_text()
        a = sql.index(start)
        b = sql.index(end, a)
        by_version[version]['statements'].insert(0, sql[a:b])
    claim = by_version['20250220000006']['statements']
    matches = [i for i,s in enumerate(claim) if 'CREATE OR REPLACE FUNCTION public.claim_rag_ingest_job()' in s]
    if len(matches) != 1:
        raise ValueError('Unexpected historical claim function')
    claim.insert(matches[0], 'DROP FUNCTION IF EXISTS public.claim_rag_ingest_job();')
    prelude('20260529120000', '20260531000400_activate_billing_core.sql',
            'CREATE TABLE IF NOT EXISTS public.billing_plans', '-- billing_events')
    prelude('20260703170000', '20260708150000_notifications.sql',
            'CREATE TABLE IF NOT EXISTS public.notifications (', 'ALTER TABLE public.notifications')
    prelude('20260705050000', '20260709200000_extended_intelligence_engine.sql',
            'CREATE TABLE IF NOT EXISTS public.organization_process_inventory (',
            'CREATE INDEX IF NOT EXISTS idx_organization_process_inventory_org')
    prelude('20260811175745', '20260811180000_platform_knowledge_fabric.sql',
            'CREATE TABLE IF NOT EXISTS public.knowledge_sources (',
            'CREATE TABLE IF NOT EXISTS public.knowledge_documents')
    guard = by_version['20260719180000']['statements']
    matches = [i for i,s in enumerate(guard) if 'INSERT INTO public.test_credential_org_allowlist' in s]
    if len(matches) != 1:
        raise ValueError('Unexpected test-org seed')
    guard[matches[0]] = """INSERT INTO public.test_credential_org_allowlist (org_id,note)
SELECT 'f07e57c0-1501-4000-8000-c04e57a00001'::uuid,'gravitre-isolated-conversation-smoke'
WHERE EXISTS (SELECT 1 FROM public.organizations WHERE id='f07e57c0-1501-4000-8000-c04e57a00001'::uuid)
ON CONFLICT (org_id) DO NOTHING;"""
    # Actual production column, absent from recorded table CREATE. Do not skip its index.
    by_version['20260805221000']['statements'].insert(0,
        'ALTER TABLE public.runs ADD COLUMN IF NOT EXISTS triggered_by uuid;')
    return rows


if __name__ == '__main__':
    original, destination = map(Path, sys.argv[1:])
    destination.write_text(json.dumps(build(json.loads(original.read_text()), Path('supabase/migrations')), indent=2)+'\n')
    destination.chmod(0o600)
