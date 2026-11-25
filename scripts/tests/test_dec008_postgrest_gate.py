"""The mandatory gate must refuse partial or skipped test reports."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dec008_gate",ROOT/"backend/scripts/run_dec008_postgrest_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class RequiredPostgrestGate(unittest.TestCase):
    def report(self,count,child=""):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)/"report.xml"
        path.write_text('<testsuites><testsuite>'+''.join(
            f'<testcase name="case{i}">{child if i==0 else ""}</testcase>' for i in range(count)
        )+'</testsuite></testsuites>')
        return path

    def test_twenty_complete_cases_pass(self):
        self.assertEqual(gate.require_complete_junit(self.report(20)),20)

    def test_missing_or_extra_cases_fail(self):
        for count in (0,19,21):
            with self.subTest(count=count),self.assertRaises(ValueError):
                gate.require_complete_junit(self.report(count))

    def test_skips_failures_and_errors_fail(self):
        for child in ('<skipped/>','<failure/>','<error/>'):
            with self.subTest(child=child),self.assertRaises(ValueError):
                gate.require_complete_junit(self.report(20,child))

    def test_canonical_gate_keeps_exact_head_and_no_softening(self):
        import json
        source=json.loads((ROOT/'docs/delivery/master-qa-workflow-source-contracts.json').read_text())
        job=source['master-qa-p0-synthetic']['jobs']['actual-runtime-and-postgres']
        checkout=next(s for s in job['steps'] if s.get('uses')=='actions/checkout@v4')
        self.assertEqual(checkout['with']['ref'],'${{ github.event.pull_request.head.sha || github.sha }}')
        install=next(s for s in job['steps'] if s.get('name')=='Install pinned real PostgREST for DEC-008')
        self.assertIn('335ea29f00145705fb569b1268b9c8e53d062f8f6f9188192e92ea3781d2dca1',install['run'])
        self.assertIn('sha256sum --check',install['run'])
        step=next(s for s in job['steps'] if s.get('name')=='DEC-008 real PostgREST reader and consumer gate (zero skips)')
        self.assertEqual(step['run'],'PYTHONPATH=. python scripts/run_dec008_postgrest_gate.py')
        self.assertNotIn('if',step)
        self.assertFalse(step.get('continue-on-error',False))
        self.assertNotIn('continue-on-error',job)

    def test_expanded_gate_requires_thirty_one(self):
        from unittest.mock import patch
        with patch.object(gate, "run_gate", return_value=0) as run:
            self.assertEqual(gate.main(), 0)
            self.assertEqual(run.call_args.kwargs["count"], 31)
        self.assertEqual(gate.require_complete_junit(self.report(31), count=31), 31)
        with self.assertRaises(ValueError):
            gate.require_complete_junit(self.report(25), count=31)
