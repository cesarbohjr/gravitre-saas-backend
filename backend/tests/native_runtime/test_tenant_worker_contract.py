"""Credential framing must fail closed without reflecting secret values."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'native-workers'))
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
