"""Credential framing must fail closed without reflecting secret values."""
from pathlib import Path
import sys
from io import BytesIO
from unittest.mock import Mock

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
        assert '.trycloudflare.com/page' in url
        matches = second_serves_fixture and 'fixture-1' in url
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
        assert evidence == [{'outcome': 'unexpected_fixture_response'}, {'outcome': 'ready'}]
    else:
        with pytest.raises(TimeoutError, match='https_fixture_unavailable'):
            contract.start_fixture_tunnel(tmp_path, 'http://127.0.0.1:8888', owned_page, evidence)
        processes[1].terminate.assert_called_once()
        assert evidence == [{'outcome': 'unexpected_fixture_response'}] * 2
    processes[0].terminate.assert_called_once()
