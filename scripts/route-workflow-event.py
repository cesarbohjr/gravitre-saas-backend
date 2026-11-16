#!/usr/bin/env python3
"""Fail-closed routing of canonical lanes using the retained source triggers.

This module never invokes a source command, provider or deployment. Git is used
only to enumerate exact changed paths; missing comparison history is an error.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
import urllib.parse
import zipfile

REPOSITORY = 'cesarbohjr/gravitre-saas-backend'
ALIASES = {'QA 01-core': ['CI'],
           'QA 11-release': ['Production release verification', 'Railway backend production']}
MAX_BYTES = 1024 * 1024


def glob_match(value, pattern):
    if any(c in pattern for c in '?[]+'):
        raise ValueError('Unsupported filter syntax; review before routing: ' + pattern)
    result, i = '', 0
    while i < len(pattern):
        if pattern[i:i+3] == '**/':
            result += '(?:.*/)?'
            i += 3
        elif pattern[i:i+2] == '**':
            result += '.*'
            i += 2
        elif pattern[i] == '*':
            result += '[^/]*'
            i += 1
        else:
            result += re.escape(pattern[i])
            i += 1
    return re.fullmatch(result, value) is not None


def any_filter(value, patterns):
    accepted = False
    for pattern in patterns:
        excluded = pattern.startswith('!')
        if glob_match(value, pattern[1:] if excluded else pattern):
            accepted = not excluded
    return accepted


def changed_paths(event_name, event, root):
    if event_name == 'pull_request':
        base, head = event['pull_request']['base']['sha'], event['pull_request']['head']['sha']
        separator = '...'
    elif event_name == 'push':
        if event.get('deleted'):
            return []
        base, head = event['before'], event['after']
        separator = '..'
        if base == '0' * 40:
            raise ValueError('New-branch push comparison requires separate source-trigger certification')
    else:
        raise ValueError('Changed paths requested for unsupported event')
    if not all(re.fullmatch('[0-9a-fA-F]{40}', sha) for sha in (base, head)):
        raise ValueError('Invalid comparison commit identity')
    result = subprocess.run(['git', 'diff', '--name-only', '-z', base + separator + head],
                            cwd=root, capture_output=True, check=True)
    return [p for p in result.stdout.decode().split('\0') if p]


def source_matches(config, event_name, event, paths=None, upstream_names=None):
    if config is None:
        config = {}
    if event_name == 'schedule':
        return any(item.get('cron') == event.get('schedule') for item in config)
    if not isinstance(config, dict):
        raise ValueError('Unsupported event contract')
    allowed = {'branches', 'branches-ignore', 'tags', 'tags-ignore', 'paths', 'paths-ignore', 'types', 'workflows'}
    if set(config) - allowed:
        raise ValueError('Unsupported source trigger keys: ' + str(sorted(set(config) - allowed)))
    if event_name == 'pull_request':
        if event.get('action') not in config.get('types', ['opened', 'synchronize', 'reopened']):
            return False
        branch, is_tag = event['pull_request']['base']['ref'], False
    elif event_name == 'push':
        ref = event['ref']
        if ref.startswith('refs/tags/'):
            branch, is_tag = ref[len('refs/tags/'):], True
            if ('branches' in config or 'branches-ignore' in config) and not ('tags' in config or 'tags-ignore' in config):
                return False
        elif ref.startswith('refs/heads/'):
            branch, is_tag = ref[len('refs/heads/'):], False
            if ('tags' in config or 'tags-ignore' in config) and not ('branches' in config or 'branches-ignore' in config):
                return False
        else:
            raise ValueError('Unsupported ref namespace')
        if event.get('deleted'):
            return False
    elif event_name == 'workflow_run':
        run = event['workflow_run']
        if event.get('action') not in config.get('types', ['requested', 'completed']):
            return False
        if not set(config.get('workflows', [])) & set(upstream_names or [run['name']]):
            return False
        branch, is_tag = run['head_branch'], False
    else:
        raise ValueError('Unsupported automatic event: ' + event_name)
    prefix = 'tags' if is_tag else 'branches'
    if prefix in config and not any_filter(branch, config[prefix]):
        return False
    if prefix + '-ignore' in config and any_filter(branch, config[prefix + '-ignore']):
        return False
    if not is_tag and ('paths' in config or 'paths-ignore' in config):
        if paths is None:
            raise ValueError('Complete changed-file evidence required')
        if 'paths' in config and not any(any_filter(path, config['paths']) for path in paths):
            return False
        if 'paths-ignore' in config and all(any_filter(path, config['paths-ignore']) for path in paths):
            return False
    return True


def select(records, lane, event_name, event, paths=None, upstream=None):
    if event.get('repository', {}).get('full_name') != REPOSITORY:
        raise ValueError('Event repository identity mismatch')
    selected, conclusions = [], {}
    upstream_names = None
    if event_name == 'workflow_run':
        run = event['workflow_run']
        if run.get('repository', {}).get('full_name', REPOSITORY) != REPOSITORY:
            raise ValueError('Upstream repository identity mismatch')
        if run.get('head_repository', {}).get('full_name', REPOSITORY) != REPOSITORY:
            raise ValueError('Fork upstream may not enter privileged routing')
        if run['name'] in ALIASES:
            if upstream is None or upstream.get('run_id') != run['id'] or upstream.get('head_sha') != run['head_sha']:
                raise ValueError('Canonical upstream evidence missing or bound to another run')
            upstream_names = [name for name in ALIASES[run['name']] if name in upstream['source_outcomes']]
        else:
            upstream_names = [run['name']]
    for record in records:
        if record['lane'] != lane:
            continue
        contract = record['automatic_trigger_contract']
        if event_name not in contract:
            continue
        config = contract[event_name]
        if isinstance(config, dict):
            config = dict(config)
            path_map = {r['source']: '.github/workflows/qa-' + r['lane'] + '.yml' for r in records}
            for key in ('paths', 'paths-ignore'):
                if key in config:
                    config[key] = [path_map.get(value, value) for value in config[key]]
        if source_matches(config, event_name, event, paths, upstream_names):
            name = Path(record['source']).stem
            selected.append(name)
            if event_name == 'workflow_run':
                names = set((config or {}).get('workflows', [])) & set(upstream_names)
                values = [upstream['source_outcomes'][n] for n in names] if upstream else [event['workflow_run']['conclusion']]
                conclusions[name] = 'success' if 'success' in values else values[0]
    derived = []
    # A release lane must not subscribe to its own workflow_run event. Preserve
    # the two former downstream edges as explicit same-run dependencies instead.
    if lane == '11-release' and set(selected) & {'production-release-verification', 'railway-backend-production'}:
        if 'release1-production-smoke' not in selected:
            selected.append('release1-production-smoke')
            derived.append('release1-production-smoke')
    return {'selected': selected, 'derived': derived, 'context_conclusions': conclusions}


def upstream_evidence(event, token):
    run = event['workflow_run']
    if run['name'] not in ALIASES:
        return None
    run_id = run.get('id')
    if not isinstance(run_id, int) or run_id <= 0:
        raise ValueError('Invalid upstream run identity')

    class SafeRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, target):
            if urllib.parse.urlsplit(target).scheme != 'https':
                raise ValueError('Non-HTTPS artifact redirect refused')
            redirected = super().redirect_request(request, response, code, message, headers, target)
            if redirected is not None and urllib.parse.urlsplit(target).netloc != 'api.github.com':
                redirected.remove_header('Authorization')
            return redirected

    def request(url):
        # URLs derive only from this fixed repository and numeric run/artifact IDs.
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token,
                                                   'Accept': 'application/vnd.github+json'})
        with urllib.request.build_opener(SafeRedirect()).open(req, timeout=30) as response:
            content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('Upstream routing evidence exceeds size limit')
        return content

    lane = {'QA 01-core': '01-core', 'QA 11-release': '11-release'}[run['name']]
    artifact_name = 'canonical-workflow-outcomes-' + lane
    payload = json.loads(request(f'https://api.github.com/repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?name={artifact_name}&per_page=100'))
    artifacts = [a for a in payload['artifacts'] if a['name'] == artifact_name and not a.get('expired')]
    if len(artifacts) != 1 or payload.get('total_count') != 1:
        raise ValueError('Unique upstream routing artifact unavailable')
    artifact_id = artifacts[0]['id']
    if not isinstance(artifact_id, int):
        raise ValueError('Invalid artifact identity')
    content = request(f'https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        member = archive.getinfo('canonical-workflow-outcomes.json')
        if member.file_size > MAX_BYTES:
            raise ValueError('Expanded routing evidence exceeds size limit')
        return json.loads(archive.read(member))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    records = json.loads((root / 'docs/delivery/master-qa-workflow-replacement-parity.json').read_text())['sources']
    event_name = os.environ['GITHUB_EVENT_NAME']
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    paths = changed_paths(event_name, event, root) if event_name in {'pull_request', 'push'} else None
    upstream = upstream_evidence(event, os.environ.get('GITHUB_TOKEN', '')) if event_name == 'workflow_run' else None
    result = select(records, args.lane, event_name, event, paths, upstream)
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        for key, value in result.items():
            output.write(key + '=' + json.dumps(value, separators=(',', ':')) + '\n')
    print('Source routing evaluated; selected count:', len(result['selected']))


if __name__ == '__main__':
    main()
