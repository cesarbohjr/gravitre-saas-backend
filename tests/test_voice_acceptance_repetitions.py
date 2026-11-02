import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('repetitions', SCRIPTS / 'voice_acceptance_repetitions.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepetitionEvidenceTests(unittest.TestCase):
    def test_failed_manifest_is_retained_and_all_scheduled_phases_run(self):
        calls = []
        def child(command, *, env, **kwargs):
            kind = 'voice' if command[1].endswith('voice_paired_live.py') else 'native'
            key = 'ACCEPTANCE_ARTIFACT_DIR' if kind == 'voice' else 'ACCEPTANCE_NATIVE_ARTIFACT_DIR'
            count = 10 if kind == 'voice' else 4
            rows = [{'status': 'PASS'} for _ in range(count)]
            if not calls:
                rows[0]['status'] = 'FAIL'
            calls.append((kind, env['PLATFORM_LIVE_BEARER_TOKEN']))
            (Path(env[key]) / 'manifest.json').write_text(json.dumps({'trials': rows}))
            return SimpleNamespace(returncode=0)

        prior = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                env = {'GITHUB_ENV': str(Path(directory) / 'github-env')}
                with patch.dict(os.environ, env), patch.object(module, 'guard'), \
                    patch('app.config.get_settings', return_value=SimpleNamespace(supabase_url=module.TARGET, supabase_service_role_key='fixture')), \
                    patch('supabase.create_client'), \
                    patch('mint_smoke_org_session.mint_session', return_value=('fixture-token', 'fixture-org')) as mint, \
                    patch('mint_smoke_org_session.export_to_github'), patch.object(module.subprocess, 'run', side_effect=child):
                    with self.assertRaises(SystemExit):
                        module.main()
                report = json.loads(Path('acceptance-results/repeated-paired/manifest.json').read_text())
                self.assertEqual(mint.call_count, 6)
                self.assertEqual(len(calls), 6)
                self.assertEqual(report['status'], 'FAIL')
                self.assertEqual(report['runs'][0]['status'], 'FAIL')
                self.assertTrue(all(r['status'] == 'PASS' for r in report['runs'][1:]))
                self.assertFalse(report['certified'])
            finally:
                os.chdir(prior)


if __name__ == '__main__':
    unittest.main()
