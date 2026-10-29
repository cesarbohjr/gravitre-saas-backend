"""Curated software-only Engineering/IT tranche; reference checks never grant tools."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from app.capabilities.agency_enrichment import SOURCE_REPO, SOURCE_REVISION
from app.capabilities.agent_manifest import render_agent_guidance
from app.core.safe_dict import safe_normalize_stored_dict

APPROVAL='PR581:user-approved-software-engineering-it-support'
_DATA=json.loads(Path(__file__).with_suffix('.json').read_text())
if _DATA['schema_version'] != 1 or _DATA['source_revision'] != SOURCE_REVISION:
    raise ValueError('unpinned_software_roles')
ROLES=tuple(_DATA['roles'])
EXCLUDED=tuple(_DATA['excluded'])


def role_for_slug(slug: str) -> dict | None:
    return next((r for r in ROLES if r['target_slug']==slug),None)


def reference(role: dict) -> dict:
    return {'version':1,'target_slug':role['target_slug'],'approval_reference':APPROVAL,
            'source_repo':SOURCE_REPO,'source_revision':SOURCE_REVISION,'license':'MIT',
            'sources':[{k:s[k] for k in ('slug','source_path','source_sha256')} for s in role['sources']]}


def render_software_role(agent: dict[str, Any]) -> str:
    config=safe_normalize_stored_dict(agent.get('config'))
    role=role_for_slug(str(config.get('marketplaceSlug') or ''))
    ref=config.get('software_guidance')
    if not role or not isinstance(ref,dict) or type(ref.get('version')) is not int or ref!=reference(role):
        return ''
    return '\n'.join([f"Software specialist: {role['name']}",render_agent_guidance(role['manifest_role']) or '',
        'Bounded source specialties: '+'; '.join(s['specialty'] for s in role['sources'])+'.',
        *['- '+g for g in role['guidance']],
        '- Software and software-centric IT only. No hardware, physical equipment, device repair or embedded firmware execution.',
        '- Reuse shared Gravitre intelligence, memory, dialogue and evaluation for text and voice. Tenant isolation, current connector access, quotas, cancellation and write approvals remain authoritative. No role or supplied code can grant tools.'])
