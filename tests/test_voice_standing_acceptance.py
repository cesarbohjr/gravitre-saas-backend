import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('standing', Path(__file__).resolve().parents[1] / 'scripts/voice_standing_acceptance.py')
standing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(standing)


class StandingAcceptanceTests(unittest.TestCase):
    def test_process_group_cleanup_handles_exit_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'child.log'
            self.assertEqual(standing.run_bounded([sys.executable, '-c', 'print("fixture")'],
                env={}, log=log, timeout=5), 0)
            self.assertEqual(standing.run_bounded([sys.executable, '-c', 'import time; time.sleep(10)'],
                env={}, log=log, timeout=.05), 124)

    def env(self):
        return dict(GRAVITRE_VOICE_ISOLATED='1', SUPABASE_URL=standing.TARGET,
            E2E_SUPABASE_ALLOWED_URL=standing.TARGET,
            ISOLATED_CONVERSATION_TEST_ORG_ID=standing.ORG,
            ISOLATED_CONVERSATION_TEST_USER_ID='fixture', SUPABASE_SERVICE_ROLE_KEY='fixture',
            SUPABASE_JWT_SECRET='fixture', ANTHROPIC_API_KEY='fixture', ACCEPTANCE_SOURCE_SHA='fixture')

    def test_acceptance_target_only(self):
        standing.validate_environment(self.env())
        for name, value in (('SUPABASE_URL', 'https://production.supabase.co'),
                            ('LIVE_API_BASE', 'https://api.gravitre.app'),
                            ('ISOLATED_CONVERSATION_TEST_ORG_ID', 'customer-org'),
                            ('GRAVITRE_VOICE_ISOLATED', '0')):
            with self.subTest(name=name), self.assertRaises(ValueError):
                standing.validate_environment({**self.env(), name: value})

    def test_portable_report_removes_arbitrary_keys_and_bodies(self):
        result = standing.portable({'status': 'FAIL', 'cases': [{'ok': False,
            'prompt': 'sensitive prompt', 'error': 'Authorization: Bearer private-token'}],
            'private-token-in-key': 'secret', 'count': 3})
        text = json.dumps(result)
        for secret in ('private-token', 'sensitive prompt', 'Authorization', 'secret'):
            self.assertNotIn(secret, text)
        self.assertEqual(result['status'], 'FAIL')
        self.assertFalse(result['cases'][0]['ok'])
        self.assertEqual(result['count'], 3)

    def test_all_batteries_execute_and_failed_first_result_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, raw = root / 'output', root / 'raw'
            output.mkdir(); raw.mkdir(); (root / 'docs/delivery').mkdir(parents=True)
            calls = []
            def child(command, *, env, log, timeout):
                i = len(calls)
                calls.append(command)
                filename = standing.BATTERIES[i][2]
                (root / 'docs/delivery' / filename).write_text(json.dumps({'status': 'FAIL' if i == 0 else 'PASS', 'cases': [{'ok': i != 0}]}))
                log.write_text('fixed fixture diagnostics')
                return 0  # contradictory child exit must not erase its FAIL report
            report = {'batteries': []}
            with patch.object(standing, 'ROOT', root), patch.object(standing, 'run_bounded', side_effect=child):
                standing.run_batteries({}, output, raw, report)
            self.assertEqual(len(calls), 7)
            self.assertEqual(report['batteries'][0]['status'], 'FAIL')
            self.assertTrue(all(r['status'] == 'PASS' for r in report['batteries'][1:]))
            self.assertEqual(json.loads((output / 'manifest.json').read_text())['batteries'][0]['status'], 'FAIL')

    def test_zero_exit_cannot_override_nonpassing_or_contradictory_report(self):
        reports = [
            {'verdict': 'PARTIAL'}, {'status': 'RUNNING'}, {'verdict': 'UNKNOWN'},
            {'verdict': 'PASS', 'status': 'FAIL'}, {'ok': False}, {'ok': 1},
            {'verdict': None}, {'status': True}, {'status': 'NOT RUN'},
            {'status': 'PASS', 'ok': True}, {'verdict': 'pass'},
            {'unified_live': {'instrumentation_present': True}},
        ]
        for data in reports:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output, raw = root / 'output', root / 'raw'
                output.mkdir(); raw.mkdir(); (root / 'docs/delivery').mkdir(parents=True)
                def child(command, *, env, log, timeout):
                    (root / 'docs/delivery/result.json').write_text(json.dumps(data))
                    log.write_text('fixed fixture diagnostics')
                    return 0
                report = {'batteries': []}
                with patch.object(standing, 'ROOT', root), patch.object(
                        standing, 'BATTERIES', (('fixture', 'fixture.py', 'result.json'),)), patch.object(
                        standing, 'run_bounded', side_effect=child):
                    standing.run_batteries({}, output, raw, report)
                expected = 'PASS' if data in reports[-3:] else 'FAIL'
                self.assertEqual(report['batteries'][0]['status'], expected)
                self.assertTrue((output / 'result.json').exists())
                self.assertTrue((raw / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()

