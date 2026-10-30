"""Copied secret whitespace must not break canonical HTTP/1.1 DB requests."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest
from pydantic import ValidationError
from app.config import Settings
from app.core import db


def settings(**extra):
    return Settings(_env_file=None, app_env='dev', supabase_url='https://fixture.invalid',
        supabase_anon_key='anon-fixture', supabase_jwt_secret='unchanged-jwt-fixture', **extra)


def test_boundary_whitespace_is_removed():
    configured = settings(supabase_service_role_key=' \nservice-fixture\r\n')
    assert configured.supabase_service_role_key == 'service-fixture'
    assert configured.supabase_jwt_secret == 'unchanged-jwt-fixture'


@pytest.mark.parametrize('token', ['', ' \n ', 'secret fixture', 'secret\nfixture', 'secret\x00fixture'])
def test_internal_or_empty_credential_refused_without_disclosing_value(token):
    with pytest.raises(ValidationError) as caught:
        settings(supabase_service_role_key=token)
    assert 'input_value=' not in str(caught.value)
    assert 'input_type=' not in str(caught.value)


def test_actual_canonical_http1_request_accepts_copied_secret():
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.headers.get('apikey'), self.headers.get('authorization')))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'[]')
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    db.clear_shared_service_clients()
    configured = settings(supabase_service_role_key='service-fixture\n')
    configured.supabase_url = 'http://127.0.0.1:' + str(server.server_port)
    client = None
    try:
        client = db.get_supabase_client(configured)
        assert client.table('organizations').select('id').execute().data == []
        assert received == [('service-fixture', 'Bearer service-fixture')]
    finally:
        if client is not None:
            client.postgrest.session.close()
        db.clear_shared_service_clients()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
