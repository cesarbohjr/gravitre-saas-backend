"""Tenant-local Flower client over the existing deployed retrieval ranker."""
from __future__ import annotations

from typing import Any

import numpy as np
from flwr.client import NumPyClient
from flwr.clientapp import ClientApp
from flwr.client.mod import secaggplus_mod

from app.ml.federated_learning import verified_privacy_profile
from app.ml.federated_runtime.privacy import runtime_settings, current_permission, feature_schema_digest, reserve_privacy_release, private_contribution


class TenantRankerClient(NumPyClient):
    def __init__(self, org_id: str):
        self.org_id = org_id

    def get_parameters(self, config: dict[str, Any]):
        # Public initialization only. No private parameters on a get-parameters
        # request that might not pass through the secure aggregation modifier.
        return [np.zeros(5, dtype=np.float64)]

    def fit(self, parameters, config):
        import os
        import json
        import base64
        from pathlib import Path
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from app.ml.federated_projection import parameter_aad
        if os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('BLOB_READ_WRITE_TOKEN'):
            raise ValueError('Tenant nodes must not hold source database or artifact-store master keys')
        settings = runtime_settings()
        profile, digest = verified_privacy_profile(settings)
        if config.get('audit_digest') != digest or config.get('program_id') != profile['program_id']:
            raise ValueError('Server requested a different audited privacy program')
        if feature_schema_digest() != profile['feature_schema_sha256']:
            raise ValueError('Audited retrieval feature schema differs from this deployment')
        current_permission(self.org_id,settings,digest)
        encoded = config.get('sealed_parameters')
        if not isinstance(encoded,str) or len(encoded) > 8192:
            raise ValueError('Bounded encrypted source parameters required')
        envelope = json.loads(encoded)
        if not isinstance(envelope,dict) or set(envelope) != {'schema','encrypted_key','nonce','ciphertext'}:
            raise ValueError('Invalid encrypted parameter envelope')
        if envelope.get('schema') != 1:
            raise ValueError('Encrypted source parameters required')
        private = serialization.load_pem_private_key(Path(os.environ['FEDERATED_PARAMETER_PRIVATE_KEY_FILE']).read_bytes(),password=None)
        if not isinstance(private,rsa.RSAPrivateKey) or not 3072 <= private.key_size <= 8192:
            raise ValueError('Enrolled tenant parameter decryption key required')
        aad = parameter_aad(self.org_id,config['round_id'],digest)
        key = private.decrypt(base64.b64decode(envelope['encrypted_key'],validate=True),
            padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
        plaintext = AESGCM(key).decrypt(base64.b64decode(envelope['nonce'],validate=True),
                                      base64.b64decode(envelope['ciphertext'],validate=True),aad)
        vector = np.asarray(json.loads(plaintext)['parameters'],dtype=np.float64)
        if vector.shape != (5,) or not np.isfinite(vector).all():
            raise ValueError('Invalid protected source parameter projection')
        current_permission(self.org_id, settings, digest)
        reserve_privacy_release(self.org_id, config["round_id"], profile, digest)
        protected = private_contribution(vector, profile)
        # No sample counts, raw examples, evaluation values or metadata leave
        # the tenant. Constant weight 1 is itself masked by Flower SecAgg+.
        return [protected], 1, {}

    def evaluate(self, parameters, config):
        raise ValueError("Federation cannot request private tenant evaluation data")


def client_fn(context):
    org_id = context.node_config.get("org_id")
    if not isinstance(org_id, str) or not org_id:
        raise ValueError("Enrolled tenant node identity required")
    return TenantRankerClient(org_id).to_client()


# No insecure toggle or plaintext training fallback. Flower refuses TRAIN
# messages without its secure-aggregation protocol configuration record.
app = ClientApp(client_fn=client_fn, mods=[secaggplus_mod])
