"""Exercise command retention, security contracts and fail-closed candidate checks."""
import copy
import importlib.util
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('canonical', ROOT / 'scripts/build-canonical-workflows.py')
canonical = importlib.util.module_from_spec(spec)
spec.loader.exec_module(canonical)


class CanonicalContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lanes, cls.records = canonical.build(ROOT)
        cls.contracts = json.loads((ROOT / 'docs/delivery/master-qa-workflow-source-contracts.json').read_text())

    def test_all_sources_and_jobs_have_exactly_one_destination(self):
        self.assertEqual(len(self.lanes), 12)
        actual = {str(p.relative_to(ROOT)) for p in (ROOT / '.github/workflows').glob('*.y*ml')}
        self.assertIn(actual, [{r['source'] for r in self.records},
                               {'.github/workflows/' + filename for filename in self.lanes}])
        self.assertEqual(sum(len(r['jobs']) for r in self.records), 122)
        for record in self.records:
            source = self.contracts[Path(record['source']).stem]
            target = self.lanes['qa-' + record['lane'] + '.yml']
            self.assertEqual(set(record['jobs']), set(source['jobs']))
            self.assertEqual(record['automatic_trigger_contract'], source['on'])
            for old_id, new_id in record['jobs'].items():
                original, migrated = source['jobs'][old_id], target['jobs'][new_id]
                prefix = Path(record['source']).stem.replace('-', '_')
                restored_name = migrated['name'].replace('inputs.' + prefix + '__', 'inputs.')
                self.assertEqual(restored_name, original.get('name', old_id))
                # These fields can never be weakened by consolidation.
                for key in ('permissions', 'environment', 'timeout-minutes', 'strategy', 'services',
                            'container', 'continue-on-error'):
                    expected = original.get(key, source.get(key) if key == 'permissions' else None)
                    if key == 'permissions' and 'uses' in original:
                        expected = {**(expected or {}), 'actions': 'read', 'pull-requests': 'read'}
                    self.assertEqual(migrated.get(key), expected, (record['source'], old_id, key))
                old_needs = original.get('needs', [])
                old_needs = [old_needs] if isinstance(old_needs, str) else old_needs
                expected_needs = ['dispatch_contract'] + [record['jobs'][n] for n in old_needs]
                if Path(record['source']).stem == 'release1-production-smoke':
                    expected_needs.extend(['production_release_verification__verify',
                                           'railway_backend_production__detect-backend-changes',
                                           'railway_backend_production__deploy'])
                self.assertEqual(migrated['needs'], expected_needs)
                self.assertIn("needs.dispatch_contract.result == 'success'", migrated['if'])
                self.assertIn("contains(fromJSON(needs.dispatch_contract.outputs.selected), '" + Path(record['source']).stem + "')", migrated['if'])

    def test_steps_and_artifacts_are_retained_without_command_softening(self):
        for record in self.records:
            source = self.contracts[Path(record['source']).stem]
            target = self.lanes['qa-' + record['lane'] + '.yml']
            prefix = Path(record['source']).stem.replace('-', '_')
            for old_id, new_id in record['jobs'].items():
                original, migrated = source['jobs'][old_id], target['jobs'][new_id]
                if 'steps' not in original:
                    continue
                steps, expected_steps = copy.deepcopy(migrated['steps']), copy.deepcopy(original['steps'])
                for step, expected_step in zip(steps, expected_steps):
                    if 'if' in expected_step:
                        step['if'] = expected_step['if'] = '<preserved-condition-with-context-remap>'
                normalized = json.dumps(steps, sort_keys=True)
                # Independent inverse of the documented namespace-only changes.
                normalized = normalized.replace('(inputs.isolated_acceptance__suite || inputs.suite)', 'inputs.suite')
                normalized = normalized.replace('inputs.' + prefix + '__', 'inputs.')
                for old, new in record['jobs'].items():
                    normalized = normalized.replace('needs.' + new, 'needs.' + old)
                # Expressions are semantically whitespace-insensitive.
                expected = json.dumps(expected_steps, sort_keys=True)
                for owner in self.records:
                    expected = expected.replace(owner['source'], '.github/workflows/qa-' + owner['lane'] + '.yml')
                normalized = re.sub(r'\$\{\{.*?\}\}', '<actions-context-expression>', normalized)
                expected = re.sub(r'\$\{\{.*?\}\}', '<actions-context-expression>', expected)
                self.assertEqual(normalized, expected, (record['source'], old_id))

    def test_manual_inputs_keep_types_defaults_choices_and_selected_requiredness(self):
        for record in self.records:
            source = self.contracts[Path(record['source']).stem]
            target = self.lanes['qa-' + record['lane'] + '.yml']
            original_inputs = (source['on'].get('workflow_dispatch') or {}).get('inputs', {})
            fields = target['on']['workflow_dispatch']['inputs']
            self.assertLessEqual(len(fields), 10)
            prefix = Path(record['source']).stem.replace('-', '_')
            for name, config in original_inputs.items():
                migrated = fields[prefix + '__' + name]
                for key in ('type', 'default', 'options'):
                    self.assertEqual(config.get(key), migrated.get(key))
            guard = next(s for s in target['jobs']['dispatch_contract']['steps'] if s.get('id') == 'contract')
            schema = json.loads(guard['env']['SOURCE_SCHEMAS'])
            self.assertEqual(schema[Path(record['source']).stem], original_inputs)

    def test_dispatch_validator_rejects_other_sources_and_missing_required_approval(self):
        lane = self.lanes['qa-12-independent-acceptance.yml']
        step = next(s for s in lane['jobs']['dispatch_contract']['steps'] if s.get('id') == 'contract')
        def validate(values):
            env = dict(os.environ, **step['env'])
            env['DISPATCH_VALUES'] = json.dumps(values)
            env['EVENT_NAME'] = 'workflow_dispatch'
            with tempfile.NamedTemporaryFile() as output:
                env['GITHUB_OUTPUT'] = output.name
                return subprocess.run([sys.executable, '-c', step['run']], env=env, capture_output=True, text=True)
        self.assertNotEqual(validate({'source': 'not-a-source'}).returncode, 0)
        result = validate({'source': 'master-qa-p27-sandbox-readback'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Required selected-source input missing', result.stderr)
        # No source commands run: this validates form data, not provider approval.
        self.assertEqual(validate({'source': 'master-qa-p0-synthetic'}).returncode, 0)

    def test_automatic_events_are_explicit_and_no_original_concurrency_collision(self):
        for filename, lane in self.lanes.items():
            self.assertTrue(set(lane['on']) <= {'workflow_dispatch', 'workflow_call', 'push', 'pull_request', 'schedule', 'workflow_run'})
            self.assertNotIn(lane['name'], lane['on'].get('workflow_run', {}).get('workflows', []))
            if filename == 'qa-01-core.yml':
                self.assertEqual(lane['concurrency'], self.contracts['ci']['concurrency'])
            else:
                self.assertIn("format('candidate-{0}'", lane['concurrency']['group'])
            self.assertFalse('permissions' in lane)  # permissions remain source/job-specific

    def test_source_outcomes_expose_results_without_passing_job_output_payloads(self):
        for lane in self.lanes.values():
            env = lane['jobs']['source_outcomes']['steps'][0]['env']
            self.assertNotIn('toJSON(needs)', env['JOB_RESULTS'])
            results = json.loads(env['JOB_RESULTS'])
            self.assertTrue(all(set(value) == {'result'} for value in results.values()))

    def test_pr_routing_has_no_actions_metadata_token(self):
        for lane in self.lanes.values():
            route = lane['jobs']['dispatch_contract']
            self.assertEqual(route['permissions'], {'contents': 'read'})
            step = next(s for s in route['steps'] if s.get('id') == 'contract')
            self.assertNotIn('GITHUB_TOKEN', step['env'])
            upstream = lane['jobs']['upstream_contract']
            self.assertEqual(upstream['if'], "${{ github.event_name == 'workflow_run' }}")
            self.assertEqual(upstream['steps'][0]['with']['ref'], '${{ github.sha }}')

    def test_skipped_metadata_reader_cannot_skip_required_source_jobs(self):
        core = self.lanes['qa-01-core.yml']['jobs']
        required = {'Backend (pytest)', 'Dependency audit', 'Integration Smoke Test',
                    'Shared runtime text/voice gate', 'Web (lint + typecheck + build)'}
        jobs = [job for job in core.values() if job.get('name') in required]
        self.assertEqual(len(jobs), 5)
        for job in jobs:
            self.assertIn('always()', job['if'])
            self.assertIn('!cancelled()', job['if'])
            self.assertNotRegex(job['if'], r'\bsuccess\s*\(')
        billing = core['ci__billing-e2e']
        self.assertIn("needs.ci__backend.result == 'success'", billing['if'])
        self.assertIn("needs.ci__web.result == 'success'", billing['if'])

    def test_cancellation_conditions_retain_boolean_type(self):
        for lane in self.lanes.values():
            self.assertNotIn('format(', lane['concurrency']['cancel-in-progress'])
        core = self.lanes['qa-01-core.yml']['concurrency']['cancel-in-progress']
        self.assertIn("github.event_name == 'pull_request'", core)

    def test_bare_step_approval_conditions_use_namespaced_inputs(self):
        jobs = self.lanes['qa-11-release.yml']['jobs']
        conditions = [step.get('if', '') for step in jobs['railway_safety_vars__safety-vars']['steps']]
        self.assertIn("inputs.railway_safety_vars__mode == 'apply'", conditions)
        self.assertNotIn("inputs.mode == 'apply'", conditions)
        cutover = jobs['unified_turn_phase4_cutover__cutover']
        self.assertIn("inputs.unified_turn_phase4_cutover__enable_live == 'true'",
                      [step.get('if', '') for step in cutover['steps']])

    def test_reusable_acceptance_calls_resolve_inside_twelve_file_layout(self):
        for lane in self.lanes.values():
            for job in lane['jobs'].values():
                if job.get('uses', '').startswith('./.github/workflows/'):
                    filename = job['uses'].rsplit('/', 1)[1]
                    self.assertIn(filename, self.lanes)
                    self.assertIn('workflow_call', self.lanes[filename]['on'])

    def test_reusable_acceptance_keeps_call_inputs_when_caller_event_is_dispatch(self):
        lane = self.lanes['qa-12-independent-acceptance.yml']
        step = next(s for s in lane['jobs']['dispatch_contract']['steps'] if s.get('id') == 'contract')
        env = dict(os.environ, **step['env'])
        env['EVENT_NAME'] = 'workflow_dispatch'
        env['DISPATCH_VALUES'] = json.dumps({'source': 'isolated-acceptance', 'suite': 'billing', '_reusable': True})
        with tempfile.NamedTemporaryFile() as output:
            env['GITHUB_OUTPUT'] = output.name
            result = subprocess.run([sys.executable, '-c', step['run']], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('isolated-acceptance', Path(output.name).read_text())

    def test_tampered_candidate_cannot_pass_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for directory in ('.github/workflows', '.github/workflow-candidates', 'scripts', 'docs/delivery'):
                shutil.copytree(ROOT / directory, root / directory)
            path = root / '.github/workflow-candidates/qa-04-governed-execution.yml'
            path.write_text(path.read_text().replace("needs.dispatch_contract.result == 'success'", 'always()', 1))
            with self.assertRaisesRegex(ValueError, 'candidate differs'):
                canonical.generate(root, check=True)

    def test_required_check_evidence_matches_retained_core_names(self):
        report = canonical.generate(ROOT, check=True)
        self.assertEqual(set(report['required_contexts']), {
            'Backend (pytest)', 'Dependency audit', 'Integration Smoke Test',
            'Shared runtime text/voice gate', 'Web (lint + typecheck + build)',
        })
        self.assertFalse(report['retirement_authorized'])

    def test_initialization_remote_readiness_is_manual_and_has_no_expired_default(self):
        source = self.contracts['acceptance-db-preflight']
        remote = source['jobs']['schema-preflight']
        self.assertIn("github.event_name == 'workflow_dispatch'", remote['if'])
        self.assertEqual(remote['needs'], ['static-contracts'])
        config = source['on']['workflow_dispatch']['inputs']['verified_migration_run_id']
        self.assertTrue(config['required'])
        self.assertNotIn('default', config)
        static = source['jobs']['static-contracts']
        self.assertEqual(static['permissions'], {'contents': 'read'})
        self.assertNotIn('secrets.', json.dumps(static))
        self.assertIn('test_acceptance_initialization_preflight.py', json.dumps(static))

    def test_yaml_loader_preserves_on_and_boolean_input_types(self):
        import yaml
        data = yaml.load('on:\n  workflow_dispatch:\n    inputs:\n      approved:\n        type: boolean\n        default: false\n', Loader=canonical.Loader)
        self.assertIn('on', data)
        self.assertIs(data['on']['workflow_dispatch']['inputs']['approved']['default'], False)


if __name__ == '__main__':
    unittest.main()
