#!/usr/bin/env python3
"""Read-only isolated-org fixture discovery. Never clones credentials or mutates vendors."""
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ORG='f07e57c0-1501-4000-8000-c04e57a00001'
BASE='https://api.gravitre.app'

def execute(output):
    token=os.environ.get('PLATFORM_LIVE_BEARER_TOKEN','')
    if (not token or os.environ.get('PLATFORM_LIVE_ORG_ID')!=ORG
            or os.environ.get('PLATFORM_LIVE_AUTH_MODE')!='smoke_org_short_lived'):
        raise SystemExit('Isolated short-lived smoke-org session required')
    headers={'Authorization':'Bearer '+token,'X-Org-Id':ORG,'X-Environment':'production'}
    def get(path):
        req=urllib.request.Request(BASE+path,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=60) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as exc:
            return exc.code,{}
    report={'schema':'gravitre.seven_intelligence.live_preflight.v1','org_id':ORG,
        'mutation':False,'provider_fixtures_certified':False,'connectors':[],'plays':[]}
    status,body=get('/health')
    report['health']={'http_status':status,'git_sha':body.get('git_sha')}
    status,body=get('/api/connectors')
    report['connectors_http_status']=status
    for row in body.get('connectors',body.get('items',[])):
        cfg=row.get('config') if isinstance(row.get('config'),dict) else {}
        report['connectors'].append({'vendor':row.get('type') or row.get('vendor'),
            'status':row.get('status'),'isolated_smoke':cfg.get('isolated_smoke') is True,
            'shares_operator_install':bool(cfg.get('cloned_from')),
            'dedicated_sandbox_proven':False})
    for key in ('customer-rescue','revenue-recovery','process-drift-detector'):
        status,body=get(f'/api/plays/{key}/readiness')
        ready=body.get('readiness') or {}
        inst_status,installation=get(f'/api/plays/{key}/installation')
        row=installation.get('installation') or {}
        report['plays'].append({'play_key':key,'readiness_http_status':status,
            'act_with_approval_ready':ready.get('act_with_approval_ready') is True,
            'installation_http_status':inst_status,'installed':bool(row),
            'operating_mode':row.get('operating_mode') or row.get('operatingMode')})
    report['remaining_fixture_requirements']=[
        'Authorized disposable provider record IDs for customer support, sales and IT incident scenarios',
        'Dedicated sandbox integrations or explicit controlled test-record scope; connector presence alone is not proof',
        'Independent provider readback for each live cell; internal assignment readback is a separate baseline']
    dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'mutation':False,'connectors_http_status':report['connectors_http_status'],
        'connector_count':len(report['connectors']),'provider_fixtures_certified':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    execute(parser.parse_args().output)
