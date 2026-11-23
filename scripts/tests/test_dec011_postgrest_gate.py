"""Fail-closed DEC-011 gate and independent DEC-008/canonical retention."""
import importlib.util
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dec011_shared_gate", ROOT/"backend/scripts/run_dec008_postgrest_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
SHA = "a"*40


def junit(count, child=""):
    return '<testsuites><testsuite>'+''.join(
        f'<testcase name="case{i}">{child if i==0 else ""}</testcase>' for i in range(count)
    )+'</testsuite></testsuites>'


class DepartmentGate(unittest.TestCase):
    def invoke(self, *, expected=SHA, checkout=SHA, postgrest="PostgREST 16.6",
               postgres="postgres (PostgreSQL) 18.7 (fixture)", dirty=False,
               binary_exists=True, returncode=0, cases=6, child=""):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root/"postgrest"
            if binary_exists:
                binary.touch()
            calls = []

            def output(command, **_kwargs):
                if command == [str(binary), "--version"]:return postgrest
                if command == ["git", "rev-parse", "HEAD"]:return checkout
                if command == [str(root/"postgres"), "--version"]:return postgres
                raise AssertionError(command)

            def run(command, **_kwargs):
                calls.append(command)
                report=Path(next(p.split("=",1)[1] for p in command if p.startswith("--junitxml=")))
                report.write_text(junit(cases,child))
                return SimpleNamespace(returncode=returncode)

            old_cwd=Path.cwd()
            try:
                os.chdir(root)
                with (
                    patch.dict(os.environ,{"GRAVITRE_POSTGREST_BIN":str(binary),"DEC011_EXPECTED_SHA":expected}),
                    patch.dict(sys.modules,{"tests.db.pg_harness":SimpleNamespace(PG_BIN=root)}),
                    patch.object(gate.subprocess,"check_output",side_effect=output),
                    patch.object(gate.subprocess,"check_call",
                                 side_effect=subprocess.CalledProcessError(1,["git","diff"]) if dirty else None),
                    patch.object(gate.subprocess,"run",side_effect=run),
                    redirect_stdout(io.StringIO()),
                ):
                    status=gate.run_gate(
                        finding="DEC-011",test_file="tests/test_dec011_department_memory_postgrest.py",
                        count=6,output_name="dec011-postgrest-evidence.json",
                        expected_sha_env="DEC011_EXPECTED_SHA",strict_checkout=True,expected_pg_version="18.7")
                evidence=json.loads((root/"dec011-postgrest-evidence.json").read_text())
            finally:
                os.chdir(old_cwd)
            return status,evidence,calls

    def test_complete_execution_has_exact_sha_and_sanitized_limits(self):
        status,evidence,calls=self.invoke()
        self.assertEqual(status,0)
        self.assertEqual(evidence['status'],'PASS')
        self.assertEqual((evidence['git_sha'],evidence['tests'],evidence['skipped']),(SHA,6,0))
        self.assertFalse(evidence['external_project_used'])
        self.assertFalse(evidence['certifies_whole_finding'])
        self.assertEqual(evidence['provider_acceptance'],'NOT_RUN')
        self.assertIn('tests/test_dec011_department_memory_postgrest.py',calls[0])

    def test_wrong_checkout_prevents_execution(self):
        status,evidence,calls=self.invoke(checkout='b'*40)
        self.assertEqual(status,1)
        self.assertEqual(calls,[])
        self.assertEqual(evidence['status'],'FAILED')

    def test_missing_explicit_sha_prevents_execution(self):
        status,_evidence,calls=self.invoke(expected='')
        self.assertEqual((status,calls),(1,[]))

    def test_dirty_checkout_prevents_execution(self):
        status,_evidence,calls=self.invoke(dirty=True)
        self.assertEqual((status,calls),(1,[]))

    def test_missing_binary_prevents_execution(self):
        status,_evidence,calls=self.invoke(binary_exists=False)
        self.assertEqual((status,calls),(1,[]))

    def test_wrong_postgrest_version_prevents_execution(self):
        status,_evidence,calls=self.invoke(postgrest='PostgREST 16.5')
        self.assertEqual((status,calls),(1,[]))

    def test_wrong_postgres_version_prevents_execution(self):
        status,_evidence,calls=self.invoke(postgres='postgres (PostgreSQL) 18.6')
        self.assertEqual((status,calls),(1,[]))

    def test_pytest_failure_cannot_produce_pass(self):
        status,evidence,_calls=self.invoke(returncode=1)
        self.assertEqual(status,1)
        self.assertEqual(evidence['status'],'FAILED')

    def test_partial_or_extra_report_cannot_produce_pass(self):
        for count in (0,5,7):
            with self.subTest(count=count):
                status,evidence,_calls=self.invoke(cases=count)
                self.assertEqual(status,1)
                self.assertEqual(evidence['status'],'FAILED')

    def test_skipped_failed_or_error_report_cannot_produce_pass(self):
        for child in ('<skipped/>','<failure/>','<error/>'):
            with self.subTest(child=child):
                status,evidence,_calls=self.invoke(child=child)
                self.assertEqual(status,1)
                self.assertEqual(evidence['status'],'FAILED')

    def test_default_validator_still_requires_twenty_for_dec008(self):
        with tempfile.TemporaryDirectory() as directory:
            report=Path(directory)/'report.xml'
            report.write_text(junit(6))
            with self.assertRaises(ValueError):gate.require_complete_junit(report)
            report.write_text(junit(20))
            self.assertEqual(gate.require_complete_junit(report),20)

    def test_canonical_six_case_gate_is_required_and_retains_independent_twenty_case_gate(self):
        contracts=json.loads((ROOT/'docs/delivery/master-qa-workflow-source-contracts.json').read_text())
        job=contracts['master-qa-p0-synthetic']['jobs']['actual-runtime-and-postgres']
        steps=job['steps']
        old=next(s for s in steps if s.get('name')=='DEC-008 real PostgREST reader and consumer gate (zero skips)')
        new=next(s for s in steps if s.get('name')=='DEC-011 real PostgREST department reader and consumer gate (zero skips)')
        self.assertEqual(old['run'],'PYTHONPATH=. python scripts/run_dec008_postgrest_gate.py')
        self.assertEqual(new['run'].splitlines(),[
            "python -m unittest discover -s ../scripts/tests -p 'test_dec*_postgrest_gate.py'",
            'PYTHONPATH=. python scripts/run_dec011_postgrest_gate.py',
        ])
        self.assertEqual(new['env']['DEC011_EXPECTED_PG_VERSION'],'18.7')
        self.assertEqual(new['env']['DEC011_EXPECTED_SHA'],'${{ github.event.pull_request.head.sha || github.sha }}')
        for step in (old,new):
            self.assertNotIn('if',step)
            self.assertNotIn('continue-on-error',step)
        self.assertNotIn('continue-on-error',job)
        checkout=next(s for s in steps if s.get('uses')=='actions/checkout@v4')
        self.assertFalse(checkout['with']['persist-credentials'])
        self.assertEqual(checkout['with']['ref'],new['env']['DEC011_EXPECTED_SHA'])
        install=next(s for s in steps if s.get('name')=='Install pinned real PostgREST for DEC-008')
        self.assertIn('335ea29f00145705fb569b1268b9c8e53d062f8f6f9188192e92ea3781d2dca1',install['run'])
        self.assertIn('sha256sum --check',install['run'])
        artifact=next(s for s in steps if s.get('name')=='Retain sanitized DEC-011 PostgREST evidence')
        self.assertEqual(artifact['if'],'${{ always() }}')
        self.assertEqual(artifact['with']['if-no-files-found'],'error')
        self.assertEqual(artifact['with']['path'],'backend/dec011-postgrest-evidence.json')
