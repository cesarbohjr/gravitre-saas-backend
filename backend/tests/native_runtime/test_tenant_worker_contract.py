"""Credential framing must fail closed without reflecting secret values."""
from pathlib import Path
import sys
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
import socket
import ssl

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'native-workers'))
import tenant_worker_contract as contract
from tenant_worker_contract import normalize_acceptance_headers, AcceptanceCredentialError


def test_copied_outer_whitespace_is_removed_before_header_construction():
    values={'E2E_SUPABASE_ANON_KEY':' \nfixture-anon\t',
            'E2E_SUPABASE_SERVICE_ROLE_KEY':'fixture-service\r\n'}
    normalized=normalize_acceptance_headers(values)
    assert set(normalized)==set(values)
    assert values=={'E2E_SUPABASE_ANON_KEY':'fixture-anon','E2E_SUPABASE_SERVICE_ROLE_KEY':'fixture-service'}


def test_embedded_control_space_and_nonascii_are_rejected_without_echo():
    for secret in ('fixture\nvalue','fixture\x00value','fixture value','fixture\u200bvalue',' \n '):
        values={'E2E_SUPABASE_ANON_KEY':'fixture-anon','E2E_SUPABASE_SERVICE_ROLE_KEY':secret}
        try:normalize_acceptance_headers(values)
        except AcceptanceCredentialError as error:
            assert error.credential_name=='E2E_SUPABASE_SERVICE_ROLE_KEY'
            assert str(error)=='Acceptance API credential is not a valid HTTP header token'
            assert secret not in str(error)
        else:raise AssertionError('Malformed header credential accepted')



def test_lost_ack_acceptance_has_bounded_extended_terminal_wait():
    from tenant_worker_contract import terminal_wait_budget
    assert terminal_wait_budget('lost_submit_ack') == 150
    assert terminal_wait_budget('lost_approval_ack') == 150
    assert terminal_wait_budget('broker_crash_after_effect') == 100
    assert terminal_wait_budget('broker_crash_before_dispatch') == 100
    assert terminal_wait_budget('approved') == 60
    assert terminal_wait_budget('denied') == 60


@pytest.mark.parametrize('error,expected', [
    (socket.gaierror('private-host'), 'dns_resolution'),
    (ssl.SSLCertVerificationError('private-host'), 'tls_certificate'),
    (ssl.SSLError('private-host'), 'tls_handshake'),
    (TimeoutError('private-host'), 'connection_timeout'),
    (ConnectionRefusedError('private-host'), 'connection_refused'),
    (ConnectionResetError('private-host'), 'connection_reset'),
    (OSError('private-host'), 'transport_other'),
])
@pytest.mark.parametrize('wrapped', [False, True])
def test_fixture_transport_diagnostics_do_not_export_exception_messages(error, expected, wrapped):
    assert contract.fixture_transport_failure(URLError(error) if wrapped else error) == expected


@pytest.mark.parametrize('second_serves_fixture', [True, False])
def test_fixture_readiness_retries_once_without_accepting_an_unrelated_page(
    tmp_path, monkeypatch, second_serves_fixture
):
    owned_page = b'<h1>Owned fixture</h1>'
    processes = []

    def popen(_command, *, stdout, **_kwargs):
        origin = f'https://fixture-{len(processes)}.trycloudflare.com'
        stdout.write(f'https://api.trycloudflare.com\n{origin}\n'.encode())
        stdout.flush()
        process = Mock()
        process.poll.return_value = None
        processes.append(process)
        return process

    def get(url, *, timeout):
        assert timeout == 5
        assert url == 'http://127.0.0.1:8888/page' or '.trycloudflare.com/page' in url
        matches = url.startswith('http://127.0.0.1:') or (second_serves_fixture and 'fixture-1' in url)
        response = BytesIO(owned_page if matches else b'<h1>Different fixture</h1>')
        response.status = 200
        response.geturl = lambda: url
        return response

    def wait(predicate, seconds, category):
        assert seconds == 45
        result = predicate()
        if result is None:
            raise TimeoutError(category)
        return result

    monkeypatch.setenv('CLOUDFLARED_BIN', 'unused-test-binary')
    monkeypatch.setattr(contract.subprocess, 'Popen', popen)
    monkeypatch.setattr(contract, 'urlopen', get)
    monkeypatch.setattr(contract, 'wait_for', wait)
    evidence = []

    if second_serves_fixture:
        process, origin = contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', owned_page, evidence)
        assert (process, origin) == (processes[1], 'https://fixture-1.trycloudflare.com')
        processes[1].terminate.assert_not_called()
        assert [row['outcome'] for row in evidence] == ['unexpected_fixture_response', 'ready']
    else:
        with pytest.raises(TimeoutError, match='https_fixture_unavailable'):
            contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', owned_page, evidence)
        processes[1].terminate.assert_called_once()
        assert [row['outcome'] for row in evidence] == ['unexpected_fixture_response'] * 2
    assert all(row['local_probe'] == {'outcome': 'ready'} for row in evidence)
    assert all(not any(row['tunnel_diagnostics'].values()) for row in evidence)
    processes[0].terminate.assert_called_once()


@pytest.mark.parametrize(('reason', 'category'), [
    (socket.gaierror(-2, 'private-host secret'), 'dns_resolution'),
    (ssl.SSLCertVerificationError('private certificate secret'), 'tls_certificate'),
    (ssl.SSLError('private handshake secret'), 'tls_handshake'),
    (TimeoutError('private endpoint secret'), 'connection_timeout'),
    (ConnectionRefusedError('private port secret'), 'connection_refused'),
    (ConnectionResetError('private connection secret'), 'connection_reset'),
    (OSError('unclassified secret'), 'transport_other'),
    ('arbitrary private reason secret', 'transport_other'),
])
def test_fixture_probe_classifies_transport_without_exporting_private_text(monkeypatch, reason, category):
    def fail(*_args, **_kwargs):
        raise URLError(reason)
    monkeypatch.setattr(contract, 'urlopen', fail)
    result = contract.fixture_probe('https://private-host/page#secret', b'owned')
    assert result == {'outcome': 'origin_unreachable', 'error_category': category}
    assert 'secret' not in str(result) and 'private' not in str(result)


@pytest.mark.parametrize('failure', ['refused', 'wrong_page'])
def test_local_fixture_must_be_exact_before_tunnel_process_starts(tmp_path, monkeypatch, failure):
    popen = Mock()
    def get(url, *, timeout):
        assert url == 'http://127.0.0.1:8888/page' and timeout == 5
        if failure == 'refused':
            raise URLError(ConnectionRefusedError('secret'))
        response = BytesIO(b'unrelated')
        response.status = 200
        response.geturl = lambda: url
        return response
    monkeypatch.setattr(contract, 'urlopen', get)
    monkeypatch.setattr(contract.subprocess, 'Popen', popen)
    evidence = []
    with pytest.raises(TimeoutError, match='local_fixture_unavailable'):
        contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', b'owned', evidence)
    popen.assert_not_called()
    assert evidence[0]['outcome'] == 'local_fixture_unavailable'
    assert evidence[0]['local_probe']['outcome'] != 'ready'
    assert 'secret' not in str(evidence)


@pytest.mark.parametrize(('status', 'redirect', 'body'), [
    (200, False, b'owned'), (200, False, b'owned extra'),
    (200, True, b'owned'), (503, False, b'owned'),
])
def test_probe_preserves_exact_status_url_and_bounded_body(monkeypatch, status, redirect, body):
    response = BytesIO(body)
    response.status = status
    response.geturl = lambda: 'https://other/page' if redirect else 'https://fixture/page'
    monkeypatch.setattr(contract, 'urlopen', lambda *_args, **_kwargs: response)
    result = contract.fixture_probe('https://fixture/page', b'owned')
    assert result == {'outcome': 'ready' if status == 200 and not redirect and body == b'owned' else 'unexpected_fixture_response'}


def test_http_error_retains_only_status_and_closes_response(monkeypatch):
    response = BytesIO(b'secret body')
    error = HTTPError('https://secret-host/page', 502, 'secret reason', {}, response)
    def fail(*_args, **_kwargs):
        raise error
    monkeypatch.setattr(contract, 'urlopen', fail)
    assert contract.fixture_probe('https://fixture/page', b'owned') == {'outcome': 'origin_http_error', 'http_status': 502}
    assert response.closed


def test_tunnel_diagnostics_exports_only_allowlisted_booleans(tmp_path):
    log = tmp_path / 'private.log'
    log.write_text('secret https://private-host cap=private-token\nRegistered tunnel connection\n'
                   'Unable to reach the origin service secret\nFailed to serve tunnel connection secret\n')
    assert contract.tunnel_diagnostics(log) == {
        'connection_registered': True, 'origin_connection_error': True, 'edge_connection_error': True,
    }


def test_failed_tunnels_preserve_sanitized_diagnostics_before_cleanup(tmp_path, monkeypatch):
    processes = []
    def popen(_command, *, stdout, **_kwargs):
        stdout.write(b'https://fixture.trycloudflare.com\nRegistered tunnel connection\n'
                     b'Unable to reach the origin service secret-token\n')
        stdout.flush()
        process = Mock()
        process.poll.return_value = None
        processes.append(process)
        return process
    def get(url, *, timeout):
        if url.startswith('https:'):
            raise URLError(socket.gaierror(-2, 'secret-host'))
        response = BytesIO(b'owned')
        response.status = 200
        response.geturl = lambda: url
        return response
    def wait(predicate, seconds, category):
        assert seconds == 45
        assert predicate() is None
        raise TimeoutError(category)
    monkeypatch.setenv('CLOUDFLARED_BIN', 'unused-test-binary')
    monkeypatch.setattr(contract.subprocess, 'Popen', popen)
    monkeypatch.setattr(contract, 'urlopen', get)
    monkeypatch.setattr(contract, 'wait_for', wait)
    evidence = []
    with pytest.raises(TimeoutError, match='https_fixture_unavailable'):
        contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', b'owned', evidence)
    assert len(processes) == 2
    for process in processes:
        process.terminate.assert_called_once()
    for row in evidence:
        assert row == {
            'outcome': 'origin_unreachable', 'error_category': 'dns_resolution',
            'transport_failures': {'dns_resolution': 1},
            'local_probe': {'outcome': 'ready'},
            'tunnel_diagnostics': {'connection_registered': True, 'origin_connection_error': True,
                                   'edge_connection_error': False},
        }
    assert 'secret' not in str(evidence)


def test_real_independent_receiver_probe_has_zero_effects(tmp_path):
    fixture = contract.IndependentFixture(tmp_path / 'effects.sqlite3', b'owned', capability='private-cap')
    try:
        assert contract.fixture_probe(fixture.origin + '/page', b'owned') == {'outcome': 'ready'}
        assert contract.fixture_probe(fixture.origin + '/page', b'other') == {'outcome': 'unexpected_fixture_response'}
        assert fixture.writes == 0
    finally:
        fixture.close()


@pytest.mark.parametrize('exited', [False, True])
def test_tunnel_without_ready_endpoint_fails_and_cleans_up(tmp_path, monkeypatch, exited):
    processes = []
    def popen(_command, *, stdout, **_kwargs):
        stdout.write(b'private-token Registered tunnel connection\n')
        stdout.flush()
        process = Mock()
        process.poll.return_value = 7 if exited else None
        processes.append(process)
        return process
    def wait(predicate, seconds, category):
        assert seconds == 45
        assert predicate() is None
        raise TimeoutError(category)
    monkeypatch.setenv('CLOUDFLARED_BIN', 'unused-test-binary')
    monkeypatch.setattr(contract, 'fixture_probe', lambda *_args: {'outcome': 'ready'})
    monkeypatch.setattr(contract.subprocess, 'Popen', popen)
    monkeypatch.setattr(contract, 'wait_for', wait)
    evidence = []
    with pytest.raises(TimeoutError, match='https_fixture_process_exited' if exited else 'https_fixture_unavailable'):
        contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', b'owned', evidence)
    assert len(processes) == 2
    for row, process in zip(evidence, processes):
        assert row['outcome'] == ('process_exited' if exited else 'origin_not_announced')
        assert row['tunnel_diagnostics']['connection_registered'] is True
        if exited:
            assert row['returncode'] == 7
            process.terminate.assert_not_called()
        else:
            process.terminate.assert_called_once()
    assert 'private-token' not in str(evidence)


def test_unreachable_fixture_records_transport_category_and_still_blocks(tmp_path, monkeypatch):
    processes = []

    def popen(_command, *, stdout, **_kwargs):
        stdout.write(b'https://fixture-private.trycloudflare.com\n')
        stdout.flush()
        process = Mock()
        process.poll.return_value = None
        processes.append(process)
        return process

    def get(url, *, timeout):
        if url.startswith('https:'):
            raise URLError(socket.gaierror('sensitive-url-and-token'))
        response = BytesIO(b'owned')
        response.status = 200
        response.geturl = lambda: url
        return response

    def wait(predicate, seconds, category):
        assert seconds == 45
        assert predicate() is None
        assert predicate() is None
        raise TimeoutError(category)

    monkeypatch.setenv('CLOUDFLARED_BIN', 'unused-test-binary')
    monkeypatch.setattr(contract.subprocess, 'Popen', popen)
    monkeypatch.setattr(contract, 'urlopen', get)
    monkeypatch.setattr(contract, 'wait_for', wait)
    evidence = []
    with pytest.raises(TimeoutError, match='https_fixture_unavailable'):
        contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', b'owned', evidence)
    assert len(evidence) == 2
    for row in evidence:
        assert row['outcome'] == 'origin_unreachable'
        assert row['error_category'] == 'dns_resolution'
        assert row['transport_failures'] == {'dns_resolution': 2}
        assert row['local_probe'] == {'outcome': 'ready'}
    assert 'sensitive-url-and-token' not in str(evidence)
    assert len(processes) == 2
    for process in processes:
        process.terminate.assert_called_once()



def test_private_fixture_route_is_exact_and_production_resolver_stays_private_deny(monkeypatch):
    from private_https_fixture import FixtureRoute, FixtureSocket
    from app.services.native_runtime.network import public_addresses
    host='qa-'+'a'*32+'.example.invalid'
    route=FixtureRoute(host,'172.17.0.1',23456)
    assert route.resolve(host)==['172.17.0.1']
    for other in ('host.docker.internal','localhost','other.example.invalid','172.17.0.1'):
        with pytest.raises(ValueError):route.resolve(other)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *_a,**_kw:[(socket.AF_INET,socket.SOCK_STREAM,0,'',('172.17.0.1',443))])
    with pytest.raises(ValueError):public_addresses(host)
    delegate=Mock()
    transport=FixtureSocket(route,delegate)
    assert transport.create_connection(('172.17.0.1',443),timeout=10)==delegate.create_connection.return_value
    delegate.create_connection.assert_called_once_with(('172.17.0.1',23456),timeout=10)
    for address in (('172.17.0.1',80),('172.17.0.2',443),('127.0.0.1',443)):
        with pytest.raises(ValueError):transport.create_connection(address)
    assert delegate.create_connection.call_count==1


@pytest.mark.parametrize('host,address,port',[
    ('other.example.invalid','172.17.0.1',23456),
    ('qa-'+'a'*32+'.example.invalid','127.0.0.1',23456),
    ('qa-'+'a'*32+'.example.invalid','169.254.169.254',23456),
    ('qa-'+'a'*32+'.example.invalid','8.8.8.8',23456),
    ('qa-'+'a'*32+'.example.invalid','172.17.0.1',443),
])
def test_private_route_rejects_invalid_scope(host,address,port):
    from private_https_fixture import FixtureRoute
    with pytest.raises(ValueError):FixtureRoute(host,address,port)


def test_real_private_tls_receiver_validates_identity_and_exact_page(tmp_path,monkeypatch):
    from private_https_fixture import issue_fixture_certificate, probe_private_https
    host='qa-'+'b'*32+'.example.invalid'
    ca,cert,key=issue_fixture_certificate(tmp_path,host)
    fixture=contract.IndependentFixture(tmp_path/'effects.sqlite3',b'owned',capability='private-cap',
        tls={'bind':'127.0.0.1','cert':str(cert),'key':str(key)})
    try:
        # Ensure the probe uses the numeric address, even if all public DNS fails.
        original=socket.getaddrinfo
        def numeric_only(name,*args,**kwargs):
            assert name=='127.0.0.1'
            return original(name,*args,**kwargs)
        monkeypatch.setattr(socket,'getaddrinfo',numeric_only)
        probe_private_https('127.0.0.1',fixture.port,host,ca,b'owned')
        with pytest.raises(ssl.SSLCertVerificationError):
            probe_private_https('127.0.0.1',fixture.port,host,None,b'owned')
        with pytest.raises(ssl.SSLCertVerificationError):
            probe_private_https('127.0.0.1',fixture.port,'wrong.example.invalid',ca,b'owned')
        with pytest.raises(ValueError,match='Unexpected disposable fixture response'):
            probe_private_https('127.0.0.1',fixture.port,host,ca,b'other')
        assert fixture.writes==0
        assert not (tmp_path/'ca.key').exists()
    finally:fixture.close()


def test_fixture_browser_wrapper_refuses_certificate_bypass():
    from private_https_fixture import CHROMIUM_WRAPPER
    import subprocess
    for flag in ('--ignore-certificate-errors','--ignore-certificate-errors-spki-list=abc','--allow-insecure-localhost'):
        result=subprocess.run(['sh','-c',CHROMIUM_WRAPPER,'chromium',flag],
            env={'HOME':'/workspace','PATH':'/usr/bin:/bin'},capture_output=True)
        assert result.returncode==1
        assert b'Certificate bypass forbidden' in result.stderr
