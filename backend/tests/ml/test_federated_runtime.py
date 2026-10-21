"""Optional real Flower/PyDP interfaces; never authorize production federation."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from app.ml.federated_runtime.privacy import reserve_privacy_release, private_contribution, feature_schema_digest


def test_tenant_privacy_reservations_survive_process_restart_and_never_reset(tmp_path, monkeypatch):
    monkeypatch.setenv('FEDERATED_RUNTIME_DATA_DIR',str(tmp_path))
    profile = {'program_id':'test-only','max_rounds':2,'noise_multiplier':10.,'delta':1e-5,'max_epsilon':10.}
    reserve_privacy_release('org','a'*64,profile,'audit')
    with pytest.raises(ValueError,match='already reserved'): reserve_privacy_release('org','a'*64,profile,'audit')
    reserve_privacy_release('org','b'*64,profile,'audit')
    with pytest.raises(ValueError,match='exhausted'): reserve_privacy_release('org','c'*64,profile,'audit')
    with pytest.raises(ValueError,match='changed'): reserve_privacy_release('org','d'*64,profile,'different-audit')
    assert len(feature_schema_digest()) == 64


def test_actual_google_dp_noise_uses_replace_one_sensitivity():
    pytest.importorskip('pydp')
    # Capture the actual sampler's scale, while still drawing real library noise.
    from pydp.distributions import GaussianDistribution
    scales = []
    def sampler(scale): scales.append(scale); return GaussianDistribution(scale)
    with patch('pydp.distributions.GaussianDistribution',side_effect=sampler):
        result = private_contribution(np.array([100.,0.,0.,0.,0.]), {'clipping_norm':1.,'noise_multiplier':2.})
    assert scales == [4.] and result.shape == (5,) and np.isfinite(result).all()
    with pytest.raises(ValueError): private_contribution(np.array([float('nan')]*5), {'clipping_norm':1.,'noise_multiplier':2.})


def test_real_flower_server_rejects_sybil_nodes_and_plaintext_fedavg(tmp_path, monkeypatch):
    pytest.importorskip('flwr')
    from flwr.common import ndarrays_to_parameters
    from app.ml.federated_runtime.server import ApprovedCohortStrategy
    monkeypatch.setenv('FEDERATED_RUNTIME_DATA_DIR',str(tmp_path))
    nodes = [SimpleNamespace(node_id=i) for i in range(100)]
    roster = {f'org-{i}' for i in range(100)}
    enrollment = {str(i):f'org-{i}' for i in range(100)}
    profile = {'program_id':'test-only'}
    strategy = ApprovedCohortStrategy('a'*64,roster,enrollment,profile,'audit',SimpleNamespace(),{org:{'schema':1} for org in roster})
    manager = SimpleNamespace(all=lambda:{str(n.node_id):n for n in nodes})
    parameters = ndarrays_to_parameters([np.zeros(5)])
    with patch('app.ml.federated_runtime.server.current_permission'):
        fit = strategy.configure_fit(1,parameters,manager)
        assert len(fit) == 100 and len(set(strategy.selected.values())) == 100
        results = [(node,SimpleNamespace(parameters=parameters)) for node in nodes]
        aggregate,_ = strategy.aggregate_fit(1,results,[])
        assert (tmp_path/('candidate-'+'a'*64+'.npz')).is_file()
        results[-1] = (nodes[-1],SimpleNamespace(parameters=ndarrays_to_parameters([np.ones(5)])))
        with pytest.raises(ValueError,match='individual update'): strategy.aggregate_fit(1,results,[])
        strategy.enrollment['99']='org-0'
        with pytest.raises(ValueError,match='100 distinct'): strategy.configure_fit(1,parameters,manager)


def test_runtime_entrypoint_always_requires_mutual_tls(monkeypatch):
    from app.ml.federated_runtime.__main__ import main
    for name in ('CERT','KEY','CA'): monkeypatch.setenv(f'FEDERATED_CONTROL_TLS_{name}_FILE',f'/test/{name.lower()}.pem')
    with patch('app.ml.federated_runtime.control.runtime_profile'), patch('uvicorn.run') as run:
        main()
    import ssl
    assert run.call_args.kwargs['ssl_cert_reqs'] == ssl.CERT_REQUIRED
    assert run.call_args.kwargs['ssl_ca_certs'] == '/test/ca.pem'


def test_encrypted_tenant_contribution_is_bound_to_org_round_and_audit(tmp_path, monkeypatch):
    pytest.importorskip("flwr")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from app.ml.federated_projection import seal_parameters
    from app.ml.federated_runtime.client import TenantRankerClient
    monkeypatch.delenv('SUPABASE_SERVICE_ROLE_KEY',raising=False)
    monkeypatch.delenv('BLOB_READ_WRITE_TOKEN',raising=False)
    monkeypatch.setenv('FEDERATED_RUNTIME_DATA_DIR',str(tmp_path))
    private = rsa.generate_private_key(public_exponent=65537,key_size=3072)
    keyfile = tmp_path/'tenant.pem'
    keyfile.write_bytes(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    monkeypatch.setenv('FEDERATED_PARAMETER_PRIVATE_KEY_FILE',str(keyfile))
    public = private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    envelope = seal_parameters(np.arange(5,dtype=float),'org','a'*64,'digest',public)
    profile = {'program_id':'test','feature_schema_sha256':feature_schema_digest()}
    config = {'program_id':'test','audit_digest':'digest','round_id':'a'*64,'sealed_parameters':json.dumps(envelope)}
    with patch('app.ml.federated_runtime.client.verified_privacy_profile',return_value=(profile,'digest')), patch('app.ml.federated_runtime.client.current_permission'), patch('app.ml.federated_runtime.client.reserve_privacy_release') as reserve, patch('app.ml.federated_runtime.client.private_contribution',side_effect=lambda vector,p:vector) as protect:
        arrays,count,metrics = TenantRankerClient('org').fit([],config)
        assert np.array_equal(arrays[0],np.arange(5)) and count == 1 and metrics == {}
        reserve.assert_called_once()
        protect.assert_called_once()
        from cryptography.exceptions import InvalidTag
        # Both RSA envelope wrapping and AES-GCM are context-bound; the wrong
        # organization cannot decrypt, even with a copied private key.
        with pytest.raises((ValueError,InvalidTag)):
            TenantRankerClient('other-org').fit([],config)
        assert reserve.call_count == 1


@pytest.mark.asyncio
async def test_controller_restart_reads_source_without_redispatch_or_privacy_refund(tmp_path,monkeypatch):
    from app.ml.federated_runtime import control
    monkeypatch.setenv('FEDERATED_RUNTIME_DATA_DIR',str(tmp_path))
    with control.database() as db:
        db.execute("INSERT INTO rounds(round,program,ordinal,fingerprint,state,run_id) VALUES ('round','program',1,'fingerprint','uncertain','123')")
    from unittest.mock import AsyncMock
    source = AsyncMock(return_value={'runs':[{'run-id':123,'status':'finished:completed'}]})
    with patch.object(control,'runtime_profile'),patch.object(control,'flower_json',source):
        # A source success without the candidate is still uncertain.
        assert (await control.get_round('round'))['state'] == 'uncertain'
        (tmp_path/'candidate-round.npz').write_bytes(b'test-only-candidate')
        result = await control.get_round('round')
        assert result['state'] == 'completed' and result['model_promoted'] is False
        assert all(call.args[0] == 'ls' for call in source.call_args_list)
    with control.database() as db:
        assert db.execute('SELECT count(*) FROM rounds').fetchone()[0] == 1


def test_consent_callback_requires_distinct_scoped_service_credential():
    from app.routers.ml_admin import federation_consent_readback
    from fastapi import HTTPException
    settings = SimpleNamespace(federated_consent_service_secret='s'*32)
    with pytest.raises(HTTPException) as denied:
        federation_consent_readback('00000000-0000-0000-0000-000000000001',authorization='Bearer user-jwt',settings=settings)
    assert denied.value.status_code == 403
    with patch('app.ml.federated_learning.verified_privacy_profile',return_value=({},'digest')), patch('app.ml.training_consent.load_training_consents',return_value={'private-data':'must-not-return'}), patch('app.ml.training_consent.consent_is_approved',return_value=False):
        result = federation_consent_readback('00000000-0000-0000-0000-000000000001',authorization='Bearer '+'s'*32,settings=settings)
    assert set(result) == {'org_id','audit_digest','approved','ranker_approved'}
    assert result['approved'] is False
