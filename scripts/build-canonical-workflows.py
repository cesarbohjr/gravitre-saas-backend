#!/usr/bin/env python3
"""Build 12 staged workflow replacements without activating them.

Source automatic triggers remain installed until the replacement cutover is qualified.
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


def add_automatic_triggers(triggers, sources, lane):
    for event in ('push', 'pull_request', 'workflow_run'):
        configs = [source['on'][event] or {} for source in sources.values() if event in source['on']]
        if not configs:
            continue
        config = {}
        if all('branches' in item for item in configs):
            config['branches'] = sorted({b for item in configs for b in item['branches']})
        if event == 'pull_request':
            config['types'] = sorted({t for item in configs for t in item.get('types', ['opened', 'synchronize', 'reopened'])})
        if event == 'workflow_run':
            config['types'] = ['completed']
            names = {name for item in configs for name in item['workflows']}
            aliases = {'CI': 'QA 01-core', 'Production release verification': 'QA 11-release',
                       'Railway backend production': 'QA 11-release'}
            names.update(aliases[name] for name in list(names) if name in aliases)
            names.discard('QA ' + lane)  # same-lane edges become explicit needs
            config['workflows'] = sorted(names)
        triggers[event] = config
    schedules = {item['cron'] for source in sources.values() for item in source['on'].get('schedule', [])}
    if schedules:
        triggers['schedule'] = [{'cron': cron} for cron in sorted(schedules)]


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
    installed = {f'qa-{lane}' for lane in module.LANES}
    if actual not in (set(owners), installed):
        raise ValueError('source inventory changed; disposition additions/removals first')
    source_path = root / 'docs/delivery/master-qa-workflow-source-contracts.json'
    definitions = ({name: load(root / f'.github/workflows/{name}.yml') for name in owners}
                   if actual == set(owners) else json.loads(source_path.read_text()))
    lanes, records = {}, []
    target_paths = {f'.github/workflows/{name}.yml': f'.github/workflows/qa-{lane}.yml'
                    for name, lane in owners.items()}
    for lane in sorted(module.LANES):
        sources = {name: definitions[name] for name in module.LANES[lane].split()}
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
                '_reusable': {'type': 'boolean', 'default': True},
            }}
        add_automatic_triggers(triggers, sources, lane)
        validation = '''import json, os
schemas = json.loads(os.environ['SOURCE_SCHEMAS'])
values = json.loads(os.environ['DISPATCH_VALUES'])
event_name = os.environ['EVENT_NAME']
called = values.get('_reusable', False)
if not called and event_name not in ('workflow_dispatch', 'workflow_call'):
    import subprocess
    subprocess.run(['python', 'scripts/route-workflow-event.py', '--lane', os.environ['CANONICAL_LANE']], check=True)
    raise SystemExit(0)
source = values.get('source')
if source not in schemas:
    raise SystemExit('Unknown source workflow')
if not called and event_name == 'workflow_dispatch' and source not in json.loads(os.environ['MANUAL_SOURCES']):
    raise SystemExit('Source has no manual trigger')
if called and source != 'isolated-acceptance':
    raise SystemExit('Unsupported reusable source')
for key, config in schemas[source].items():
    value = values.get(source.replace('-', '_') + '__' + key)
    if called and key == 'suite':
        value = values.get('suite')
    if config.get('required') and (value is None or value == ''):
        raise SystemExit('Required selected-source input missing: ' + key)
print('Selected source input contract validated; this is not execution acceptance')
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write('selected=' + json.dumps([source]) + '\\n')
    output.write('derived=[]\\ncontext_conclusions={}\\n')
'''
        jobs = {'upstream_contract': {
            'name': 'Read trusted upstream outcome metadata', 'if': "${{ github.event_name == 'workflow_run' }}",
            'runs-on': 'ubuntu-latest', 'timeout-minutes': 3,
            'permissions': {'contents': 'read', 'actions': 'read'},
            'outputs': {'evidence': '${{ steps.upstream.outputs.evidence }}'},
            'steps': [{'uses': 'actions/checkout@v4', 'with': {'ref': '${{ github.sha }}', 'persist-credentials': False}},
                      {'id': 'upstream', 'run': 'python scripts/route-workflow-event.py --lane ' + lane + ' --fetch-upstream',
                       'env': {'GITHUB_TOKEN': '${{ github.token }}'}}],
        }, 'dispatch_contract': {
            'name': 'Validate selected source inputs', 'runs-on': 'ubuntu-latest',
            'permissions': {'contents': 'read'}, 'timeout-minutes': 4,
            'needs': ['upstream_contract'],
            'if': "${{ always() && (needs.upstream_contract.result == 'success' || needs.upstream_contract.result == 'skipped') }}",
            'outputs': {key: '${{ steps.contract.outputs.' + key + ' }}'
                        for key in ('selected', 'derived', 'context_conclusions')},
            'steps': [{'uses': 'actions/checkout@v4', 'with': {'persist-credentials': False, 'fetch-depth': 0}},
                      {'id': 'contract', 'name': 'Validate source contract', 'shell': 'python',
                       'env': {'SOURCE_SCHEMAS': json.dumps(schema),
                               'MANUAL_SOURCES': json.dumps(manual),
                               'DISPATCH_VALUES': '${{ toJSON(inputs) }}', 'EVENT_NAME': '${{ github.event_name }}',
                               'CANONICAL_LANE': lane, 'UPSTREAM_EVIDENCE': '${{ needs.upstream_contract.outputs.evidence }}'},
                       'run': validation}],
        }}
        groups, cancels = [], []
        for name, source in sources.items():
            prefix = name.replace('-', '_')
            job_ids = {jid: prefix + '__' + jid for jid in source['jobs']}
            input_keys = schema[name]

            def ancestors(jid, visited=None):
                visited = set() if visited is None else visited
                needs = source['jobs'][jid].get('needs', [])
                needs = [needs] if isinstance(needs, str) else needs
                for dependency in needs:
                    if dependency not in visited:
                        visited.add(dependency)
                        ancestors(dependency, visited)
                return sorted(visited)

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
                    # Canonical upstream outcomes are per former workflow, not
                    # the combined lane conclusion. A sibling failure cannot
                    # silently change another source's downstream decision.
                    # Keys in JSON retain their original hyphens, so use [] form.
                    upstream = "fromJSON(needs.dispatch_contract.outputs.context_conclusions)[" + literal(name) + "]"
                    inner = inner.replace('github.event.workflow_run.conclusion', '(' + upstream + ' || github.event.workflow_run.conclusion)')
                    if name == 'release1-production-smoke':
                        derived = "contains(fromJSON(needs.dispatch_contract.outputs.derived), 'release1-production-smoke')"
                        inner = inner.replace('github.event.workflow_run.head_sha', '(' + derived + ' && (github.event.workflow_run.head_sha || github.sha) || github.event.workflow_run.head_sha)')
                        inner = inner.replace('github.event_name', '(' + derived + " && 'workflow_run' || github.event_name)")
                        inner = inner.replace('(' + upstream + ' || github.event.workflow_run.conclusion)', '(' + derived + " && 'success' || " + upstream + ' || github.event.workflow_run.conclusion)')
                    return '${{' + inner + '}}'
                rewritten = re.sub(r'\$\{\{(.*?)\}\}', context, text, flags=re.S)
                for old_path, new_path in target_paths.items():
                    rewritten = rewritten.replace(old_path, new_path)
                return rewritten

            for jid, original in source['jobs'].items():
                job = walk(copy.deepcopy(original), rewrite)
                for step in job.get('steps', []):
                    # Step-level conditions accept bare expressions, too.
                    if isinstance(step.get('if'), str) and '${{' not in step['if']:
                        step['if'] = expression(rewrite('${{ ' + step['if'] + ' }}'))
                # Preserve the former displayed check name even for unnamed jobs.
                job.setdefault('name', jid)
                needs = original.get('needs', [])
                needs = [needs] if isinstance(needs, str) else needs
                job['needs'] = ['dispatch_contract'] + [job_ids[n] for n in needs]
                condition = original.get('if', 'success()')
                # Bare job conditions also contain Actions context references.
                condition = expression(rewrite('${{ ' + expression(condition) + ' }}'))
                dependency_ids = [job_ids[key] for key in ancestors(jid)]
                source_success = ' && '.join(f"needs.{key}.result == 'success'" for key in dependency_ids) or 'true'
                source_failure = ' || '.join(f"needs.{key}.result == 'failure'" for key in dependency_ids) or 'false'
                has_status = bool(re.search(r'\b(success|failure|cancelled|always)\s*\(', condition))
                condition = re.sub(r'\bsuccess\s*\(\s*\)', '(!cancelled() && (' + source_success + '))', condition)
                condition = re.sub(r'\bfailure\s*\(\s*\)', '(' + source_failure + ')', condition)
                if not has_status:
                    condition = '!cancelled() && (' + source_success + ') && (' + condition + ')'
                selection = 'contains(fromJSON(needs.dispatch_contract.outputs.selected), ' + literal(name) + ')'
                # Metadata-reader skips are not source failures. Scope status
                # checks to the original source graph and explicitly avoid the
                # default transitive skip behavior of added routing ancestors.
                job['if'] = "${{ always() && needs.dispatch_contract.result == 'success' && " + selection + ' && (' + condition + ') }}'
                if name == 'release1-production-smoke':
                    producers = ['production-release-verification', 'railway-backend-production']
                    successful = []
                    for producer in producers:
                        producer_ids = [producer.replace('-', '_') + '__' + key for key in sources[producer]['jobs']]
                        job['needs'].extend(producer_ids)
                        checks = [f"needs.{key}.result != 'failure' && needs.{key}.result != 'cancelled'" for key in producer_ids]
                        checks.append('(' + ' || '.join(f"needs.{key}.result == 'success'" for key in producer_ids) + ')')
                        successful.append('(' + ' && '.join(checks) + ')')
                    derived_gate = "!contains(fromJSON(needs.dispatch_contract.outputs.derived), 'release1-production-smoke') || " + ' || '.join(successful)
                    job['if'] = '${{ always() && (' + expression(job['if']) + ') && (' + derived_gate + ') }}'
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
                if job.get('uses', '').startswith('./.github/workflows/qa-'):
                    # The called route reads only upstream Actions metadata.
                    job['permissions'] = {**job.get('permissions', {}), 'actions': 'read', 'pull-requests': 'read'}
                if 'uses' not in job and source.get('concurrency'):
                    section = source['concurrency']
                    section = {'group': section} if isinstance(section, str) else section
                    group = template_expression(walk(section['group'], rewrite))
                    cancel = section.get('cancel-in-progress', False)
                    cancel = str(cancel).lower() if isinstance(cancel, bool) else expression(walk(cancel, rewrite))
                    # Distinct source jobs/matrix entries never cancel one
                    # another; repeated instances of the same resource serialize.
                    job['concurrency'] = {'group': "${{ format('candidate-{0}-{1}-{2}', " + group + ', ' + literal(job_ids[jid]) + ', toJSON(matrix)) }}',
                                          'cancel-in-progress': '${{ ' + cancel + ' }}'}
                jobs[job_ids[jid]] = job
            concurrency = source.get('concurrency')
            if concurrency:
                concurrency = {'group': concurrency} if isinstance(concurrency, str) else concurrency
                group = template_expression(walk(concurrency['group'], rewrite))
                cancel_value = concurrency.get('cancel-in-progress', False)
                # A complete expression retains its boolean type. format()
                # would turn false into the non-empty (truthy) string 'false'.
                cancel = (str(cancel_value).lower() if isinstance(cancel_value, bool)
                          else expression(walk(cancel_value, rewrite)))
                groups.append(f'(inputs.source == {literal(name)} && ({group}))')
                # false values must not fall through to another selected source;
                # clauses for other sources are false, leaving the final false.
                cancels.append(f'(inputs.source == {literal(name)} && ({cancel}))')
            records.append({'source': f'.github/workflows/{name}.yml', 'display_name': source.get('name', name), 'lane': lane,
                            'jobs': job_ids, 'automatic_trigger_contract': source.get('on', {}),
                            'manual_dispatch_supported': name in manual})
        outcome_script = '''import json, os
sources = json.loads(os.environ['SOURCE_JOBS'])
needs = json.loads(os.environ['JOB_RESULTS'])
selected = json.loads(os.environ['SELECTED'])
outcomes = {}
for name, source in sources.items():
    if name not in selected:
        continue
    results = [needs[key]['result'] for key in source['jobs']]
    outcome = ('failure' if 'failure' in results else 'cancelled' if 'cancelled' in results
               else 'success' if 'success' in results else 'skipped')
    outcomes[source['display_name']] = outcome
evidence = {'run_id': int(os.environ['GITHUB_RUN_ID']), 'head_sha': os.environ['GITHUB_SHA'],
            'source_outcomes': outcomes}
with open('canonical-workflow-outcomes.json', 'w') as output:
    json.dump(evidence, output)
'''
        source_jobs = {name: {'display_name': source.get('name', name),
                             'jobs': [name.replace('-', '_') + '__' + jid for jid in source['jobs']]}
                       for name, source in sources.items()}
        jobs['source_outcomes'] = {
            'name': 'Record independent source workflow outcomes', 'if': '${{ always() && needs.dispatch_contract.result == \'success\' }}',
            'runs-on': 'ubuntu-latest', 'timeout-minutes': 3, 'permissions': {},
            'needs': list(jobs),
            'steps': [{'name': 'Bind source outcomes to this run', 'shell': 'python', 'run': outcome_script,
                       'env': {'SOURCE_JOBS': json.dumps(source_jobs),
                               'JOB_RESULTS': json.dumps({key: {'result': '${{ needs.' + key + '.result }}'}
                                                          for values in source_jobs.values() for key in values['jobs']}),
                               'SELECTED': '${{ needs.dispatch_contract.outputs.selected }}'}},
                      {'uses': 'actions/upload-artifact@v4', 'with': {
                          'name': 'canonical-workflow-outcomes-' + lane, 'path': 'canonical-workflow-outcomes.json',
                          'if-no-files-found': 'error', 'retention-days': 14}}],
        }
        # Candidate groups are isolated from the still-active originals. The
        # cutover must remove this prefix only after originals are disabled.
        group_expr = ' || '.join(groups + ['github.run_id'])
        result = {'name': 'QA ' + lane, 'on': triggers,
                  'concurrency': {'group': "${{ format('candidate-{0}', " + group_expr + ') }}',
                                  'cancel-in-progress': '${{ ' + ' || '.join(cancels + ['false']) + ' }}'},
                  'jobs': jobs}
        if lane == '01-core':
            # Keep the protected CI run lifecycle, including cancellation of a
            # superseded PR SHA, when its filename/display name changes.
            result['concurrency'] = copy.deepcopy(sources['ci']['concurrency'])
        lanes[f'qa-{lane}.yml'] = result
    return lanes, records


def generate(root, check=False):
    lanes, records = build(root)
    protection = json.loads((root / 'docs/delivery/master-qa-required-checks-readback.json').read_text())
    required = {item['context'] for item in protection['required_status_checks']}
    contracts_path = root / 'docs/delivery/master-qa-workflow-source-contracts.json'
    if (root / '.github/workflows/ci.yml').exists():
        definitions = {Path(record['source']).stem: load(root / record['source']) for record in records}
        if check:
            if json.loads(contracts_path.read_text()) != definitions:
                raise ValueError('retained source contracts are stale')
        else:
            contracts_path.write_text(json.dumps(definitions, indent=2) + '\n')
        core = definitions['ci']
    else:
        core = load(root / '.github/workflows/qa-01-core.yml')
    current_checks = {job.get('name', jid) for jid, job in core['jobs'].items()}
    if (protection.get('branch_pattern') != 'main' or not protection.get('require_status_checks')
            or not required or not required <= current_checks
            or any(item['source_workflow'] != '.github/workflows/ci.yml' for item in protection['required_status_checks'])):
        raise ValueError('required-check readback is inconsistent with retained Core CI')
    directory = root / '.github/workflow-candidates'
    if check and {p.name for p in directory.glob('*.yml')} != set(lanes):
        raise ValueError('candidate lane count or filenames differ')
    for name, definition in lanes.items():
        path = directory / name
        if check:
            if load(path) != definition:
                raise ValueError('candidate differs from source contracts: ' + name)
            installed = root / '.github/workflows' / name
            if not (root / '.github/workflows/ci.yml').exists() and load(installed) != definition:
                raise ValueError('installed workflow differs from verified candidate: ' + name)
        else:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_text('# STAGED: not installed in .github/workflows; automatic trigger cutover pending.\n' + yaml.safe_dump(definition, sort_keys=False, width=120))
    report = {'source_count': len(records), 'candidate_count': len(lanes),
              'source_job_count': sum(len(r['jobs']) for r in records),
              'static_contract_parity': 'PASS', 'runtime_parity': 'REQUIRES_INDEPENDENT_RUN_EVIDENCE',
              'automatic_trigger_parity': 'STATIC_REPLAY_PASS_RUNTIME_PENDING',
              'automatic_source_event_contract_count': sum(
                  event not in {'workflow_dispatch', 'workflow_call'}
                  for record in records for event in record['automatic_trigger_contract']),
              'required_checks': 'VERIFIED_ADMIN_UI', 'retirement_authorized': False,
              'required_contexts': sorted(required),
              'required_checks_evidence_url': protection['evidence_url'],
              'limitations': ['Candidates implement automatic routing but remain uninstalled; source automatic triggers remain active.',
                              'Core CI retains its original run concurrency group; other candidate locks remain isolated from originals.',
                              'Automatic events use per-job/matrix resource locks; whole-source cancellation is replaced by stage cancellation and needs runtime qualification.',
                              'Repository-wide callers, protected environment workflow restrictions and exact-head runs require verification.',
                              'GitHub workflow identity changes and source-path references require explicit cutover review.',
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
    print(f"Static contracts: {report['source_count']} sources / {report['source_job_count']} jobs / {report['candidate_count']} canonical lanes; runtime certification requires independent run evidence.")
