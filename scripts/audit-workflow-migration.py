#!/usr/bin/env python3
"""Inventory source contracts; never authorize retirement from static evidence.

Requires PyYAML. Reads a checkout without invoking workflow commands or providers.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import yaml

# Explicit reviewed ownership, not filename inference. Every workflow must appear
# exactly once; additions must be dispositioned before regenerating the inventory.
LANES = {
    '01-core': 'ci repair-root-npm-lock',
    '02-identity-privacy': 'auth-config-sync credential-db-bypass-daily deletion-lifecycle-readiness msp-isolated-database-security snowflake-isolated-security release1-role-execution-matrix',
    '03-data-recovery': 'acceptance-db-preflight migration-history-recovery supabase-migration-safety pr605-gate26-postgres-outbox',
    '04-governed-execution': 'autonomous-write-certification connector-governance connector-verified-writes-live outcome-ownership-contract pr605-cross-surface-ownership pr605-run-status-contract pr605-runtime-edge-contract release1-execution-revocation-audit release1-live-approval-denial',
    '05-intelligence': 'agent-roi-live catalog-enrichment-nl-variance conversation-engineering conversation-parity-contract department-eval-suites federated-runtime golden-benchmark-live intelligence-lifecycle-e2e intelligence-offline-acceptance live-generated-response-quality milestone2-latency-ab milestone2-performance-audit native-langfuse-certification phase3-intelligence-coverage phase3-offline-12-scenarios phase3-phase5-evidence research-cascade-prod-smoke unified-turn-phase2-live unified-turn-standing-batteries',
    '06-voice': 'master-qa-qa30-acoustic-qualification master-qa-qa30-offline-cancellation master-qa-qa30-voice-confirmed-turns run-acceptance-voice voice-duplex-guard voice-gates-2-3 voice-livekit-candidate voice-slo-gates voice-stt-control-latency release1-chat-voice-revocation-e2e',
    '07-browser-product': 'authenticated-click-audit browser-fallback-recovery-certification conversational-product-acceptance desktop-tauri extension-release navigation-e2e pr605-route-inventory release1-authenticated-network-audit release1-authenticated-smoke release1-deployed-browser-credentials',
    '08-billing-marketplace': 'live-signup-billing-http marketplace-production-smoke run-acceptance-billing',
    '09-marketing': 'indexnow-on-publish marketing-lighthouse seo-publishing social-intelligence-regression',
    '10-operations': 'chat-history-hygiene-live connector-health knowledge-sync metrics-rollup msp-enrichment-workflow-live native-workers-offline platform-cs-backfill probe-gmail-live-bugs-audit smoke-conversation-pollution-cleanup unified-turn-ops-gates usage-sync workflow-schedules',
    '11-release': 'production-hardening-smoke production-release-verification railway-backend-production railway-safety-vars release1-production-smoke unified-turn-phase4-cutover',
    '12-independent-acceptance': 'eco-001-deployed-ingress isolated-acceptance master-qa-p0-synthetic master-qa-p27-sandbox-readback milestone1-live-reverify plays-datasets-live-proof plays-production-acceptance release1-live-memory-liveness release1-live-public-mcp',
}


def inventory(root, source_sha):
    owners = {}
    for lane, names in LANES.items():
        for name in names.split():
            path = f'.github/workflows/{name}.yml'
            if path in owners:
                raise ValueError(f'duplicate ownership: {path}')
            owners[path] = lane
    paths = sorted((root / '.github/workflows').glob('*.y*ml'))
    actual = {str(p.relative_to(root)) for p in paths}
    historical_count = len(owners)
    canonical = {f'.github/workflows/qa-{lane}.yml': lane for lane in LANES}
    if actual == set(canonical):
        owners = canonical
    if actual != set(owners):
        raise ValueError(f'ownership mismatch: unassigned={sorted(actual-set(owners))}, missing={sorted(set(owners)-actual)}')
    # Whole-repository literal references supplement workflow_run and uses edges.
    # Dynamic external callers cannot be established by a source scan.
    references = {path: [] for path in actual}
    for file in sorted(root.rglob('*')):
        if not file.is_file() or '.git' in file.parts or file.suffix not in {'.md', '.yml', '.yaml', '.py', '.json', '.sh', '.ts', '.tsx'}:
            continue
        rel = str(file.relative_to(root))
        if rel.endswith('master-qa-workflow-migration-inventory.json'):
            continue
        try:
            body = file.read_text()
        except (UnicodeError, OSError):
            continue
        for path in actual:
            if path in body or Path(path).name in body:
                references[path].append(rel)
    entries = []
    evidence_path = root / 'docs/delivery/master-qa-required-checks-readback.json'
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else None
    for path in paths:
        rel = str(path.relative_to(root))
        raw = path.read_bytes()
        # BaseLoader preserves GitHub's "on" key and scalar expressions verbatim.
        definition = yaml.load(raw, Loader=yaml.BaseLoader)
        if not isinstance(definition, dict) or not definition.get('jobs'):
            raise ValueError(f'invalid workflow: {rel}')
        entries.append({
            'source': rel,
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'target_lane': owners[rel],
            'status': 'CANONICAL_QA_PENDING' if actual == set(canonical) else 'MIGRATION_BLOCKED',
            'source_contract': definition,
            'secret_references': sorted(set(re.findall(r'secrets\.([A-Za-z_][A-Za-z0-9_]*)', raw.decode()))),
            'repository_literal_references': references[rel],
            'external_callers': 'UNKNOWN',
            'required_check_contexts': ([item['context'] for item in evidence['required_status_checks']]
                                       if evidence and rel in {'.github/workflows/ci.yml', '.github/workflows/qa-01-core.yml'}
                                       else [] if evidence else 'UNKNOWN'),
            'replacement_run_url': None,
            'parity_verified': False,
            'delete_safe': False,
        })
    return {
        'schema_version': 1,
        'source_commit': source_sha,
        'source_count': len(entries),
        'historical_source_count': historical_count,
        'target_lane_count': len(LANES),
        'required_checks_evidence': (evidence['evidence_url'] if evidence else
                                     'main branch-protection GET denied with HTTP 403; required checks unknown'),
        'reference_scan_scope': 'Available checkout files only; dynamic and external callers remain UNKNOWN',
        'retirement_authorized': False,
        'workflows': entries,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inventory(args.root.resolve(), args.source_sha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Inventoried {report['source_count']} workflows across {report['target_lane_count']} lanes; retirement remains blocked.")
