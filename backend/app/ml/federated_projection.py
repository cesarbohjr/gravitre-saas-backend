"""Source-side projection: encrypt canonical ranker parameters to each tenant node.

Only the existing Gravitre backend reads registry artifacts. Flower aggregation
and client containers must never receive Supabase service-role or blob RW keys.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def audited_enrollment(settings: Any, profile: dict[str, Any]) -> dict[str, dict[str, str]]:
    encoded = Path(settings.federated_node_registry_file).read_bytes()
    if len(encoded) > 2_000_000 or hashlib.sha256(encoded).hexdigest() != profile.get('node_registry_sha256'):
        raise ValueError('Tenant-node registry differs from independently audited deployment')
    records = json.loads(encoded)
    if not isinstance(records, dict) or not 100 <= len(records) <= 10000:
        raise ValueError('At least 100 enrolled tenant nodes required')
    seen = set()
    seen_keys = set()
    from uuid import UUID
    for node_id, record in records.items():
        if not isinstance(node_id, str) or not node_id.isdecimal() or not isinstance(record, dict):
            raise ValueError('Authenticated Flower node identity required')
        org = str(UUID(record.get('org_id', '')))
        if org != record['org_id'] or org in seen:
            raise ValueError('Exactly one enrolled node per tenant required')
        seen.add(org)
        pem = record.get('parameter_public_key')
        if not isinstance(pem, str) or len(pem) > 10000:
            raise ValueError('Bounded tenant parameter-encryption public key required')
        key = serialization.load_pem_public_key(pem.encode())
        if not isinstance(key, rsa.RSAPublicKey) or not 3072 <= key.key_size <= 8192:
            raise ValueError('3072-8192 bit tenant RSA parameter-encryption key required')
        fingerprint = hashlib.sha256(key.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()
        if fingerprint in seen_keys:
            raise ValueError('Tenant parameter encryption keys must be distinct')
        seen_keys.add(fingerprint)
    return records


def parameter_aad(org_id: str, round_id: str, audit_digest: str) -> bytes:
    return json.dumps({'org_id':org_id,'round_id':round_id,'audit_digest':audit_digest},sort_keys=True,separators=(',',':')).encode()


def seal_parameters(vector: np.ndarray, org_id: str, round_id: str, digest: str, public_key_pem: str) -> dict[str, str | int]:
    if vector.shape != (5,) or not np.isfinite(vector).all():
        raise ValueError('Canonical finite retrieval parameters required')
    public_key = serialization.load_pem_public_key(public_key_pem.encode())
    if not isinstance(public_key,rsa.RSAPublicKey) or not 3072 <= public_key.key_size <= 8192:
        raise ValueError('Audited tenant encryption key required')
    key, nonce = secrets.token_bytes(32), secrets.token_bytes(12)
    aad = parameter_aad(org_id,round_id,digest)
    plaintext = json.dumps({'parameters':vector.tolist()},separators=(',',':')).encode()
    wrapped = public_key.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=aad))
    encrypted = AESGCM(key).encrypt(nonce,plaintext,aad)
    return {'schema':1,'encrypted_key':base64.b64encode(wrapped).decode(),
            'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(encrypted).decode()}


async def prepare_contributions(participants: list[str], round_id: str, profile: dict[str, Any], digest: str, settings: Any):
    from app.ml.model_catalog import load_org_trained_catalog_model
    from app.ml.training_consent import training_is_approved
    enrollment = await asyncio.to_thread(audited_enrollment,settings,profile)
    keys = {row['org_id']:row['parameter_public_key'] for row in enrollment.values()}
    semaphore = asyncio.Semaphore(8)
    async def prepare(org_id):
        async with semaphore:
            if org_id not in keys or not await training_is_approved(org_id,'federated_learning',settings):
                return None
            try:
                ranker = await load_org_trained_catalog_model(org_id,'retrieval_ranker',settings=settings)
                model, scaler = getattr(ranker,'model',None),getattr(ranker,'scaler',None)
                if (not getattr(ranker,'registry_ref',None) or model is None or scaler is None
                        or list(model.classes_) != [0,1] or model.coef_.shape != (1,4)):
                    return None
                coefficients = model.coef_[0]/scaler.scale_
                vector = np.concatenate([coefficients,[model.intercept_[0]-np.dot(coefficients,scaler.mean_)]])
                return org_id,seal_parameters(vector,org_id,round_id,digest,keys[org_id]),ranker.registry_ref,datetime.now(timezone.utc).isoformat()
            except Exception:
                # One unavailable/incompatible artifact excludes this tenant;
                # it cannot weaken the 100-distinct-participant threshold.
                return None
    results = await asyncio.gather(*(prepare(org) for org in participants))
    eligible = sorted([item for item in results if item is not None],key=lambda item:item[0])[:100]
    if len(eligible) < 100:
        raise ValueError('100 enrolled, approved tenants with compatible deployed rankers required')
    from app.ml.federated_adoption import save_source_anchor
    from app.workflows.repository import get_supabase_client
    client = get_supabase_client(settings)
    for org_id,_,reference,captured_at in eligible:
        await asyncio.to_thread(save_source_anchor,client,org_id,round_id,digest,reference,captured_at)
    return {org_id:envelope for org_id,envelope,_,_ in eligible}
