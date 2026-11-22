"""Replay automatic source triggers without provider calls or GitHub writes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('event_router', ROOT / 'scripts/route-workflow-event.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)
REPO = {'full_name': router.REPOSITORY}


class EventRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = json.loads((ROOT / 'docs/delivery/master-qa-workflow-replacement-parity.json').read_text())['sources']

    def test_every_automatic_trigger_has_a_positive_replay(self):
        replays = 0
        aliases = {r['source']: '.github/workflows/qa-' + r['lane'] + '.yml' for r in self.records}
        for record in self.records:
            for event_name, config in record['automatic_trigger_contract'].items():
                if event_name in {'workflow_call', 'workflow_dispatch'}:
                    continue
                config = config or {}
                event = {'repository': REPO}
                paths = [] if event_name in {'push', 'pull_request'} else None
                if event_name == 'schedule':
                    event['schedule'] = config[0]['cron']
                else:
                    branch = config.get('branches', ['main'])[0]
                    if event_name == 'pull_request':
                        event.update(action=config.get('types', ['opened'])[0], pull_request={'base': {'ref': branch}})
                    elif event_name == 'push':
                        event['ref'] = 'refs/heads/' + branch
                    elif event_name == 'workflow_run':
                        event.update(action='completed', workflow_run={'name': config['workflows'][0], 'head_branch': branch,
                                                                      'head_sha': 'a'*40, 'id': 10, 'conclusion': 'success'})
                    if 'paths' in config:
                        pattern = next(p for p in config['paths'] if not p.startswith('!'))
                        paths = [aliases.get(pattern, pattern).replace('**', 'directory').replace('*', 'file')]
                result = router.select(self.records, record['lane'], event_name, event, paths)
                self.assertIn(Path(record['source']).stem, result['selected'], (record['source'], event_name, paths))
                replays += 1
        # Main's signed fixture registration adds one offline PR event contract.
        self.assertEqual(replays, 97)

    def test_globs_respect_directories_literal_parentheses_and_ordered_exclusions(self):
        self.assertTrue(router.glob_match('backend/tests/a.py', 'backend/**'))
        self.assertTrue(router.glob_match('backend/a.py', 'backend/**/a.py'))
        self.assertTrue(router.glob_match('apps/web/app/(app)/ai/page.tsx', 'apps/web/app/(app)/**'))
        self.assertFalse(router.glob_match('scripts/sub/a.py', 'scripts/*.py'))
        self.assertFalse(router.any_filter('backend/secrets/a.py', ['backend/**', '!backend/secrets/**']))
        self.assertTrue(router.any_filter('backend/secrets/allowed.py', ['backend/**', '!backend/secrets/**', 'backend/secrets/allowed.py']))
        with self.assertRaises(ValueError):
            router.glob_match('x', '[a-z]')

    def test_wrong_branch_and_unrelated_paths_do_not_select_provider_or_release_jobs(self):
        event = {'repository': REPO, 'ref': 'refs/heads/main'}
        for lane in ('04-governed-execution', '10-operations', '11-release'):
            selected = router.select(self.records, lane, 'push', event, ['docs/unrelated.txt'])['selected']
            self.assertNotIn('railway-backend-production', selected)
            self.assertNotIn('connector-verified-writes-live', selected)
        event['ref'] = 'refs/heads/unrelated'
        self.assertNotIn('railway-backend-production', router.select(self.records, '11-release', 'push', event, ['backend/app/main.py'])['selected'])

    def test_disposable_fixture_pr_contract_routes_to_existing_acceptance_lane(self):
        event = {'repository': REPO, 'action': 'synchronize',
                 'pull_request': {'base': {'ref': 'main'}}}
        for path in ('scripts/eco001_disposable_preflight.py',
                     'tests/test_eco001_disposable_preflight.py',
                     '.github/workflows/qa-12-independent-acceptance.yml'):
            selected = router.select(self.records, '12-independent-acceptance',
                                     'pull_request', event, [path])['selected']
            self.assertIn('eco-001-deployed-ingress', selected)
        selected = router.select(self.records, '12-independent-acceptance',
                                 'pull_request', event, ['docs/unrelated.md'])['selected']
        self.assertNotIn('eco-001-deployed-ingress', selected)

    def test_label_only_preflight_does_not_turn_into_pr_provider_writes(self):
        event = {'repository': REPO, 'action': 'synchronize', 'pull_request': {'base': {'ref': 'main'}}}
        paths = ['backend/scripts/p27_hubspot_dispatch_guard.py']
        self.assertNotIn('master-qa-p27-sandbox-readback', router.select(self.records, '12-independent-acceptance', 'pull_request', event, paths)['selected'])
        event['action'] = 'labeled'
        self.assertIn('master-qa-p27-sandbox-readback', router.select(self.records, '12-independent-acceptance', 'pull_request', event, paths)['selected'])
        # The source provider-write job still has its original workflow_dispatch
        # and approval conditions; selecting its workflow is not write permission.

    def test_canonical_upstream_requires_run_bound_independent_outcomes(self):
        event = {'repository': REPO, 'action': 'completed', 'workflow_run': {
            'name': 'QA 01-core', 'id': 25, 'head_sha': 'a'*40, 'head_branch': 'main', 'conclusion': 'failure'}}
        with self.assertRaisesRegex(ValueError, 'bound to another run'):
            router.select(self.records, '11-release', 'workflow_run', event)
        evidence = {'run_id': 25, 'head_sha': 'a'*40, 'source_outcomes': {'CI': 'success'}}
        result = router.select(self.records, '11-release', 'workflow_run', event, upstream=evidence)
        self.assertIn('production-release-verification', result['selected'])
        self.assertEqual(result['context_conclusions']['production-release-verification'], 'success')
        self.assertIn('release1-production-smoke', result['derived'])
        evidence['run_id'] = 26
        with self.assertRaises(ValueError):
            router.select(self.records, '11-release', 'workflow_run', event, upstream=evidence)

    def test_foreign_and_fork_upstreams_fail_closed(self):
        with self.assertRaises(ValueError):
            router.select(self.records, '01-core', 'push', {'repository': {'full_name': 'other/repo'}}, [])
        event = {'repository': REPO, 'action': 'completed', 'workflow_run': {
            'name': 'CI', 'head_repository': {'full_name': 'attacker/fork'}, 'head_branch': 'main', 'conclusion': 'success'}}
        with self.assertRaisesRegex(ValueError, 'Fork'):
            router.select(self.records, '11-release', 'workflow_run', event)

    def test_missing_paths_and_invalid_commits_are_not_silent_success(self):
        with self.assertRaisesRegex(ValueError, 'changed-file evidence'):
            router.source_matches({'paths': ['backend/**']}, 'push', {'ref': 'refs/heads/main'})
        with self.assertRaisesRegex(ValueError, 'commit identity'):
            router.changed_paths('push', {'before': '--malicious-option', 'after': 'a'*40}, ROOT)
        with self.assertRaisesRegex(ValueError, 'New-branch'):
            router.changed_paths('push', {'before': '0'*40, 'after': 'a'*40}, ROOT)

    def test_unchanged_tag_does_not_enter_branch_deploys(self):
        self.assertFalse(router.source_matches({'branches': ['main']}, 'push', {'ref': 'refs/tags/main'}, []))
        self.assertFalse(router.source_matches({'branches': ['main']}, 'push', {'ref': 'refs/heads/main', 'deleted': True}, []))


if __name__ == '__main__':
    unittest.main()
