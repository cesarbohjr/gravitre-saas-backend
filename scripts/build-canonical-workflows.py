#!/usr/bin/env python3
"""Build 12 staged, manual-dispatch workflow replacements without activating them.

The source workflows remain authoritative for automatic triggers until cutover.
Run --check to detect lost job contracts or stale candidates. No network calls.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path

import yaml


class Loader(yaml.SafeLoader):
    pass


# GitHub uses YAML 1.2 booleans; PyYAML's default YAML 1.1 turns 'on' into True.
Loader.yaml_implicit_resolvers = copy.deepcopy(Loader.yaml_implicit_resolvers)
for key, resolvers in Loader.yaml_implicit_resolvers.items():
    Loader.yaml_implicit_resolvers[key] = [r for r in resolvers if r[0] != 'tag:yaml.org,2002:bool']
Loader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$', re.I), list('tTfF'))


def load(path):
    return yaml.load(path.read_text(), Loader=Loader)


def expression(value):
    text = str(value).strip()
    return text[3:-2].strip() if text.startswith('${{') and text.endswith('}}') else text


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def template_expression(value):
    """Turn a string with embedded Actions expressions into one expression."""
    if isinstance(value, bool):
        return str(value).lower()
    parts = re.split(r'(\$\{\{.*?\}\})', str(value))
    args, fmt = [], ''
    for part in parts:
        if part.startswith('${{'):
            fmt += '{' + str(len(args)) + '}'
            args.append(expression(part))
        else:
            fmt += part.replace('{', '{{').replace('}', '}}')
    return 'format(' + ', '.join([literal(fmt)] + args) + ')' if args else literal(value)


def walk(value, replace):
    if isinstance(value, str):
        return replace(value)
    if isinstance(value, list):
        return [walk(v, replace) for v in value]
    if isinstance(value, dict):
        return {k: walk(v, replace) for k, v in value.items()}
    return value


def build(root):
    spec = importlib.util.spec_from_file_location('inventory', root / 'scripts/audit-workflow-migration.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    owners = {}
    for lane, names in module.LANES.items():
        for name in names.split():
            if name in owners:
                raise ValueError('duplicate source ownership: ' + name)
            owners[name] = lane
    actual = {p.stem for p in (root / '.github/workflows').glob('*.y*ml')}
    if actual != set(owners):
        raise ValueError('source inventory changed; disposition additions/removals first')
    lanes, records = {}, []
    for lane in sorted(module.LANES):
        sources = {name: load(root / f'.github/workflows/{name}.yml') for name in module.LANES[lane].split()}
        manual = [name for name, source in sources.items() if 'workflow_dispatch' in source.get('on', {})]
        if not manual:
            raise ValueError('lane has no manual entrypoint: ' + lane)
        dispatch = {'source': {'description': 'Original workflow contract to execute', 'required': True,
                               'type': 'choice', 'options': manual, 'default': manual[0]}}
        schema = {}
        for name, source in sources.items():
            inputs = (source.get('on', {}).get('workflow_dispatch') or {}).get('inputs', {})
            prefix = name.replace('-', '_')
            schema[name] = inputs
            for key, config in inputs.items():
                config = copy.deepcopy(config)
                config['description'] = f'{name}: {config.get("description", key)}'
                config['required'] = False  # selected-source validation enforces original requiredness
                dispatch[f'{prefix}__{key}'] = config
        if len(dispatch) > 10:
            raise ValueError('dispatch form exceeds 10 fields: ' + lane)
        triggers = {'workflow_dispatch': {'inputs': dispatch}}
        if lane == '12-independent-acceptance':
            triggers['workflow_call'] = {'inputs': {
                'source': {'type': 'string', 'default': 'isolated-acceptance'},
                'suite': {'type': 'string', 'required': True},
            }}
        validation = '''import json, os
schemas = json.loads(os.environ['SOURCE_SCHEMAS'])
values = json.loads(os.environ['DISPATCH_VALUES'])
source = values.get('source')
if source not in schemas:
    raise SystemExit('Unknown source workflow')
if os.environ['EVENT_NAME'] == 'workflow_dispatch' and source not in json.loads(os.environ['MANUAL_SOURCES']):
    raise SystemExit('Source has no manual trigger')
if os.environ['EVENT_NAME'] != 'workflow_dispatch' and source != 'isolated-acceptance':
    raise SystemExit('Unsupported reusable source')
for key, config in schemas[source].items():
    value = values.get(source.replace('-', '_') + '__' + key)
    if os.environ['EVENT_NAME'] != 'workflow_dispatch' and key == 'suite':
        value = values.get('suite')
    if config.get('required') and (value is None or value == ''):
        raise SystemExit('Required selected-source input missing: ' + key)
print('Selected source input contract validated; this is not execution acceptance')
'''
        jobs = {'dispatch_contract': {
            'name': 'Validate selected source inputs', 'runs-on': 'ubuntu-latest',
            'permissions': {}, 'timeout-minutes': 2,
            'steps': [{'name': 'Validate source contract', 'shell': 'python',
                       'env': {'SOURCE_SCHEMAS': json.dumps(schema),
                               'MANUAL_SOURCES': json.dumps(manual),
                               'DISPATCH_VALUES': '${{ toJSON(inputs) }}', 'EVENT_NAME': '${{ github.event_name }}'},
                       'run': validation}],
        }}
        groups, cancels = [], []
        for name, source in sources.items():
            prefix = name.replace('-', '_')
            job_ids = {jid: prefix + '__' + jid for jid in source['jobs']}
            input_keys = schema[name]

            def rewrite(text):
                # Match context expressions only; shell/local-language variables
                # named 'inputs' or 'needs' must never be modified.
                def context(match):
                    inner = match.group(1)
                    for jid, target in sorted(job_ids.items(), key=lambda kv: -len(kv[0])):
                        inner = re.sub(r'\bneeds\.' + re.escape(jid) + r'(?=\.|\b)', 'needs.' + target, inner)
                    for key in sorted(input_keys, key=len, reverse=True):
                        target = prefix + '__' + key
                        # Called isolated acceptance uses suite from workflow_call.
                        if name == 'isolated-acceptance' and key == 'suite':
                            inner = re.sub(r'\binputs\.suite\b', "(inputs.isolated_acceptance__suite || inputs.suite)", inner)
                        else:
                            inner = re.sub(r'\binputs\.' + re.escape(key) + r'\b', 'inputs.' + target, inner)
                        inner = re.sub(r'\bgithub\.event\.inputs\.' + re.escape(key) + r'\b', 'github.event.inputs.' + target, inner)
                    inner = re.sub(r'\bgithub\.workflow\b', literal(source.get('name', name)), inner)
                    return '${{' + inner + '}}'
                return re.sub(r'\$\{\{(.*?)\}\}', context, text, flags=re.S)

            for jid, original in source['jobs'].items():
                job = walk(copy.deepcopy(original), rewrite)
                # Preserve the former displayed check name even for unnamed jobs.
                job.setdefault('name', jid)
                needs = original.get('needs', [])
                needs = [needs] if isinstance(needs, str) else needs
                job['needs'] = ['dispatch_contract'] + [job_ids[n] for n in needs]
                condition = original.get('if', 'success()')
                # Bare job conditions also contain Actions context references.
                condition = expression(rewrite('${{ ' + expression(condition) + ' }}'))
                job['if'] = "${{ needs.dispatch_contract.result == 'success' && inputs.source == " + literal(name) + ' && (' + condition + ') }}'
                if 'uses' not in job:
                    for key in ('env', 'defaults'):
                        if key in source:
                            merged = walk(copy.deepcopy(source[key]), rewrite)
                            if key == 'defaults' and 'run' in job.get(key, {}):
                                merged['run'] = {**merged.get('run', {}), **job[key]['run']}
                            else:
                                merged.update(job.get(key, {}))
                            job[key] = merged
                if 'permissions' not in job and 'permissions' in source:
                    job['permissions'] = copy.deepcopy(source['permissions'])
                if job.get('uses') == './.github/workflows/isolated-acceptance.yml':
                    job['uses'] = './.github/workflows/qa-12-independent-acceptance.yml'
                jobs[job_ids[jid]] = job
            concurrency = source.get('concurrency')
            if concurrency:
                concurrency = {'group': concurrency} if isinstance(concurrency, str) else concurrency
                group = template_expression(walk(concurrency['group'], rewrite))
                cancel = template_expression(concurrency.get('cancel-in-progress', False))
                groups.append(f'(inputs.source == {literal(name)} && ({group}))')
                # false values must not fall through to another selected source;
                # clauses for other sources are false, leaving the final false.
                cancels.append(f'(inputs.source == {literal(name)} && ({cancel}))')
            records.append({'source': f'.github/workflows/{name}.yml', 'lane': lane,
                            'jobs': job_ids, 'automatic_trigger_contract': source.get('on', {}),
                            'manual_dispatch_supported': name in manual})
        # Candidate groups are isolated from the still-active originals. The
        # cutover must remove this prefix only after originals are disabled.
        group_expr = ' || '.join(groups + ['github.run_id'])
        result = {'name': 'QA ' + lane, 'on': triggers,
                  'concurrency': {'group': "${{ format('candidate-{0}', " + group_expr + ') }}',
                                  'cancel-in-progress': '${{ ' + ' || '.join(cancels + ['false']) + ' }}'},
                  'jobs': jobs}
        lanes[f'qa-{lane}.yml'] = result
    return lanes, records


def generate(root, check=False):
    lanes, records = build(root)
    directory = root / '.github/workflow-candidates'
    if check and {p.name for p in directory.glob('*.yml')} != set(lanes):
        raise ValueError('candidate lane count or filenames differ')
    for name, definition in lanes.items():
        path = directory / name
        if check:
            if load(path) != definition:
                raise ValueError('candidate differs from source contracts: ' + name)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_text('# STAGED: not installed in .github/workflows; automatic trigger cutover pending.\n' + yaml.safe_dump(definition, sort_keys=False, width=120))
    report = {'source_count': len(records), 'candidate_count': len(lanes),
              'source_job_count': sum(len(r['jobs']) for r in records),
              'static_contract_parity': 'PASS', 'runtime_parity': 'NOT_RUN',
              'automatic_trigger_parity': 'NOT_IMPLEMENTED',
              'required_checks': 'BLOCKED_ADMIN_READ', 'retirement_authorized': False,
              'limitations': ['Candidates preserve manual entrypoints only; source automatic triggers remain active.',
                              'Candidate concurrency groups intentionally cannot cancel original runs.',
                              'Repository-wide callers, protected environment workflow restrictions and exact-head runs require verification.',
                              'Local reusable acceptance calls target the eventual canonical installed path.'],
              'sources': records}
    report_path = root / 'docs/delivery/master-qa-workflow-replacement-parity.json'
    if check:
        if json.loads(report_path.read_text()) != report:
            raise ValueError('stale parity report')
    else:
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    report = generate(args.root.resolve(), check=args.check)
    print(f"Static contracts: {report['source_count']} sources / {report['source_job_count']} jobs / {report['candidate_count']} staged lanes; runtime NOT RUN; automatic cutover NOT IMPLEMENTED.")
