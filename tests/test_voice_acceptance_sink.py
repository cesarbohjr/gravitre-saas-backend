import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location('sink', Path(__file__).resolve().parents[1] / 'scripts/voice_acceptance_sink.py')
sink = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sink)


class SinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'effects.sqlite'
        self.start()

    def start(self):
        self.server = sink.server(self.path, org='isolated-org', actor='isolated-actor', token='fixture-only-token')
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def tearDown(self):
        self.stop()
        self.tmp.cleanup()

    def request(self, authorization='Bearer fixture-only-token', **changes):
        body = dict(org_id='isolated-org', actor_id='isolated-actor', logical_id='same-command',
                    action='acceptance.note.create', payload={'note': 'synthetic fixture'})
        body.update(changes)
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        try:
            connection.request('POST', '/effects', json.dumps(body),
                {'Authorization': authorization, 'Content-Type': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_positive_control_records_a_real_effect(self):
        self.assertEqual(self.request()[0], 200)
        evidence = sink.audit(self.path)
        self.assertEqual(len(evidence['attempts']), 1)
        self.assertEqual(len(evidence['effects']), 1)

    def test_duplicate_attempts_remain_visible_despite_sink_deduplication(self):
        first = self.request()[1]
        second = self.request()[1]
        self.assertEqual(first['effect_id'], second['effect_id'])
        evidence = sink.audit(self.path)
        self.assertEqual(len(evidence['attempts']), 2)
        self.assertEqual(len(evidence['effects']), 1)

    def test_wrong_tenant_is_denied_without_effect(self):
        self.assertEqual(self.request(org_id='foreign-org')[0], 403)
        self.assertEqual(sink.audit(self.path)['effects'], [])

    def test_wrong_actor_is_denied_without_effect(self):
        self.assertEqual(self.request(actor_id='foreign-actor')[0], 403)
        self.assertEqual(sink.audit(self.path)['effects'], [])

    def test_unauthenticated_attempt_is_visible_and_has_no_effect(self):
        self.assertEqual(self.request(authorization='Bearer wrong-fixture-token')[0], 401)
        evidence = sink.audit(self.path)
        self.assertEqual(evidence['effects'], [])
        self.assertEqual(evidence['attempts'][0]['status'], 401)

    def test_restart_preserves_effect_and_request_history(self):
        self.request()
        before = sink.audit(self.path)
        self.stop()
        self.start()
        self.assertEqual(sink.audit(self.path), before)


if __name__ == '__main__': unittest.main()
