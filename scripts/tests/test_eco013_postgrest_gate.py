"""The new gate cannot substitute partial or skipped execution for eight cases."""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT/"backend/scripts/run_eco013_postgrest_gate.py"
spec = importlib.util.spec_from_file_location("eco013_shared_gate", ROOT/"backend/scripts/run_dec008_postgrest_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class AuthorityGate(unittest.TestCase):
    def test_wrapper_fixes_real_file_count_and_strict_checkout(self):
        run = Mock(return_value=0)
        with patch.dict(sys.modules,{"run_dec008_postgrest_gate":SimpleNamespace(run_gate=run)}), patch.dict(os.environ,{},clear=True):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_path(str(WRAPPER),run_name="__main__")
        self.assertEqual(stopped.exception.code,0)
        run.assert_called_once_with(
            finding="ECO-013",test_file="tests/test_eco013_plan_authority_postgrest.py",count=8,
            output_name="eco013-postgrest-evidence.json",expected_sha_env="ECO013_EXPECTED_SHA",
            strict_checkout=True,expected_pg_version="18.7")

    def test_local_version_profile_requires_explicit_override(self):
        run = Mock(return_value=1)
        with patch.dict(sys.modules,{"run_dec008_postgrest_gate":SimpleNamespace(run_gate=run)}), patch.dict(os.environ,{"ECO013_EXPECTED_PG_VERSION":"16.2"}):
            with self.assertRaises(SystemExit) as stopped:
                runpy.run_path(str(WRAPPER),run_name="__main__")
        self.assertEqual(stopped.exception.code,1)
        self.assertEqual(run.call_args.kwargs['expected_pg_version'],'16.2')

    def test_only_eight_complete_cases_pass_junit_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory)/"result.xml"
            for count,child,accepted in [(8,"",True),(0,"",False),(7,"",False),(9,"",False),
                                         (8,"<skipped/>",False),(8,"<failure/>",False),(8,"<error/>",False)]:
                with self.subTest(count=count,child=child):
                    report.write_text('<testsuites><testsuite>'+''.join(
                        f'<testcase name="case{i}">{child if i==0 else ""}</testcase>' for i in range(count)
                    )+'</testsuite></testsuites>')
                    if accepted:self.assertEqual(gate.require_complete_junit(report,count=8,finding="ECO-013"),8)
                    else:
                        with self.assertRaises(ValueError):gate.require_complete_junit(report,count=8,finding="ECO-013")

    def test_canonical_gate_and_artifact_required_without_changing_reader_steps(self):
        source = json.loads((ROOT/'docs/delivery/master-qa-workflow-source-contracts.json').read_text())
        job = source['master-qa-p0-synthetic']['jobs']['actual-runtime-and-postgres']
        steps = job['steps']
        new = next(s for s in steps if s.get('name')=='ECO-013 real PostgREST terminal authority gate (zero skips)')
        self.assertNotIn('if',new); self.assertNotIn('continue-on-error',new)
        self.assertNotIn('continue-on-error',job)
        self.assertEqual(new['run'].splitlines(),[
            "python -m unittest discover -s ../scripts/tests -p 'test_eco013_postgrest_gate.py'",
            'PYTHONPATH=. python scripts/run_eco013_postgrest_gate.py'])
        self.assertEqual(new['env']['ECO013_EXPECTED_SHA'],'${{ github.event.pull_request.head.sha || github.sha }}')
        self.assertEqual(new['env']['ECO013_EXPECTED_PG_VERSION'],'18.7')
        checkout = next(s for s in steps if s.get('uses')=='actions/checkout@v4')
        self.assertEqual(checkout['with']['ref'],new['env']['ECO013_EXPECTED_SHA'])
        self.assertFalse(checkout['with']['persist-credentials'])
        old8 = next(s for s in steps if s.get('name')=='DEC-008 real PostgREST reader and consumer gate (zero skips)')
        old11 = next(s for s in steps if s.get('name')=='DEC-011 real PostgREST department reader and consumer gate (zero skips)')
        self.assertEqual(old8['run'],'PYTHONPATH=. python scripts/run_dec008_postgrest_gate.py')
        self.assertIn('scripts/run_dec011_postgrest_gate.py',old11['run'])
        artifact = next(s for s in steps if s.get('name')=='Retain sanitized ECO-013 PostgREST evidence')
        self.assertEqual(artifact['if'],'${{ always() }}')
        self.assertEqual(artifact['with']['if-no-files-found'],'error')
        self.assertEqual(artifact['with']['path'],'backend/eco013-postgrest-evidence.json')
        self.assertEqual(artifact['with']['name'],'eco013-real-postgrest-${{ github.event.pull_request.head.sha || github.sha }}')
