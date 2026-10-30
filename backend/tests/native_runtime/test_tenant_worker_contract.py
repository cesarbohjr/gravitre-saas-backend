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
