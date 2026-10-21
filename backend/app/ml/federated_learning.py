"""Federated control-plane adapter with signed audit and tenant-consent gates.

No raw records or unmasked updates pass through this adapter. Secure aggregation
and DP execute in the separately deployed, independently reviewed Flower runtime.
An unsigned JSON flag is never proof that a privacy protocol exists.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import re
import ssl
from functools import lru_cache
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.ml.base import ModelStatus, ModelType
from app.ml.catalog_base import CatalogScaffoldModel


@lru_cache(maxsize=64)
def _composed_epsilon(noise: float, rounds: int, delta: float) -> float:
    from opacus.accountants import RDPAccountant
    accountant = RDPAccountant()
    for _ in range(rounds):
        accountant.step(noise_multiplier=noise, sample_rate=1.0)
    return accountant.get_epsilon(delta=delta)


def verified_privacy_profile(settings: Any) -> tuple[dict[str, Any], str]:
    key = getattr(settings, "federated_audit_public_key", "")
    envelope = getattr(settings, "federated_audit_manifest", "")
    if not isinstance(key, str) or not key or not isinstance(envelope, str) or not envelope or len(envelope) > 32000:
        raise ValueError("Independently signed federation audit manifest required")
    document = json.loads(envelope)
    payload = document["payload"]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(
        base64.b64decode(document["signature"], validate=True), encoded)
    expiry = datetime.fromisoformat(payload["expires_at"].replace("Z", "+00:00"))
    if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
        raise ValueError("Federation audit expired")
    if (payload.get("protocol") != "flower_secaggplus" or payload.get("privacy_unit") != "organization"
            or payload.get("adjacency") != "replace_one" or payload.get("accountant") != "rdp"
            or payload.get("transport") != "mutual_tls" or payload.get("min_participants") != 100
            or payload.get("raw_data_egress") is not False):
        raise ValueError("Audited federation protocol/profile mismatch")
    for field in ("deployment_sha256", "audit_ref", "legal_review_ref", "approved_by", "program_id", "feature_schema_sha256", "node_registry_sha256"):
        if not isinstance(payload.get(field), str) or not 1 <= len(payload[field]) <= 512:
            raise ValueError("Named legal/privacy owner and deployment evidence required")
    for field in ('deployment_sha256','feature_schema_sha256','node_registry_sha256'):
        if not re.fullmatch(r'[a-f0-9]{64}',payload[field]):
            raise ValueError('SHA256 deployment, feature and node-registry identities required')
    for field in ("max_epsilon", "delta", "noise_multiplier", "clipping_norm"):
        number = payload.get(field)
        if type(number) not in {int, float} or not math.isfinite(number) or number <= 0:
            raise ValueError("Finite audited privacy parameters required")
    if payload["delta"] >= .01 or type(payload.get("max_rounds")) is not int or not 1 <= payload["max_rounds"] <= 1000:
        raise ValueError("Bounded privacy accounting profile required")
    if not 1e-12 <= payload["clipping_norm"] <= 1e12 or not 1e-3 <= payload["noise_multiplier"] <= 1e6:
        raise ValueError("Privacy parameters exceed the audited runtime's numerical range")
    # Verify accountant availability and the entire declared composition before
    # any dispatch. q=1 is conservative; never claim amplification from a made-up
    # sampling fraction. Noise is calibrated to replace-one sensitivity by the
    # audited runtime, not by this orchestration adapter.
    epsilon = _composed_epsilon(payload["noise_multiplier"], payload["max_rounds"], payload["delta"])
    if not math.isfinite(epsilon) or epsilon > payload["max_epsilon"]:
        raise ValueError("Audited profile exceeds composed privacy budget")
    return payload, hashlib.sha256(encoded).hexdigest()


class FederatedLearningCoordinator(CatalogScaffoldModel):
    model_type = ModelType.EMBEDDING
    catalog_status = ModelStatus.DISABLED
    catalog_name = "federated_learning"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        # A round coordinator is not a predictive model and cannot verify model
        # inference by returning a made-up score or accepting caller assurances.
        from app.config import get_settings
        try:
            profile, digest = await asyncio.to_thread(verified_privacy_profile, kwargs.get("settings") or get_settings())
        except Exception:
            return {"status": "disabled", "model": self.catalog_name, "reason": "DISABLED — independently audited privacy runtime required", "advisory_only": True}
        return {"status": "dormant", "reason": "consented_participants_and_attested_runtime_required",
                "audit_digest": digest, "program_id": profile["program_id"], "advisory_only": True}

    async def reconcile(self, *, org_id: str, settings: Any) -> dict[str, Any]:
        from app.core.redis_client import get_sync_redis
        from app.core.safe_dict import safe_normalize_stored_dict
        from app.ml.training_consent import consent_is_approved, load_training_consents
        from app.workflows.repository import get_supabase_client
        profile, digest = await asyncio.to_thread(verified_privacy_profile, settings)
        client = get_supabase_client(settings)
        # Discover consent records only. No tenant content, records, weights or
        # gradients are read here. Each tenant runtime retains its own data.
        rows = await asyncio.to_thread(lambda: client.table("organizations").select("id,settings").limit(10000).execute())
        participants = []
        for row in rows.data or []:
            stored = safe_normalize_stored_dict(row.get("settings"))
            consents = safe_normalize_stored_dict(stored.get("model_training_consents"))
            consent = safe_normalize_stored_dict(consents.get(self.catalog_name))
            if (consent_is_approved(consents, self.catalog_name) and consent.get("audit_digest") == digest
                    and consent.get("sharing_scope") == "cross_tenant_private_updates"):
                participants.append(row["id"])
        participants = sorted(set(participants))
        from app.ml.federated_adoption import LEDGER, TERMINAL, MAX_ADOPTION_AGE, timestamp, update_anchor
        own = next((row for row in rows.data or [] if row.get("id") == org_id),{})
        anchors = safe_normalize_stored_dict(safe_normalize_stored_dict(own.get("settings")).get(LEDGER))
        terminal = TERMINAL
        for key,raw in anchors.items():
            entry = safe_normalize_stored_dict(raw)
            if (entry.get('audit_digest') == digest and entry.get('state') not in terminal
                    and datetime.now(timezone.utc)-timestamp(entry.get('captured_at')) >= MAX_ADOPTION_AGE):
                await asyncio.to_thread(update_anchor,client,org_id,key,lambda current:{**current,'state':'expired'})
        pending = {key:value for key,raw in anchors.items()
                   if (value := safe_normalize_stored_dict(raw)).get("audit_digest") == digest
                   and value.get("state") not in terminal
                   and datetime.now(timezone.utc)-timestamp(value.get('captured_at')) < MAX_ADOPTION_AGE}
        if org_id not in participants or len(participants) < 100 and not pending:
            return {"status": "dormant", "reason": "100_current_distinct_tenant_approvals_required", "participants": len(participants)}
        url = getattr(settings, "federated_runtime_url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Configured HTTPS federation runtime required")
        context = ssl.create_default_context(cafile=settings.federated_runtime_ca_file)
        context.load_cert_chain(settings.federated_runtime_cert_file, settings.federated_runtime_key_file)
        redis = await asyncio.to_thread(get_sync_redis, settings)
        if redis is None:
            raise ValueError("Federation round coordination unavailable")
        # One global program lease. Repeated per-org background runs cannot
        # launch overlapping rounds with the same participants/privacy budget.
        lock = redis.lock(f"ml:federated:{profile['program_id']}", timeout=7200, blocking_timeout=0, thread_local=False)
        if not await asyncio.to_thread(lock.acquire, blocking=False):
            return {"status": "already_running"}
        try:
            async with httpx.AsyncClient(verify=context, timeout=30, follow_redirects=False) as runtime:
                response = await runtime.get(url.rstrip("/") + "/v1/attestation")
                response.raise_for_status()
                attestation = response.json()
                if attestation.get("deployment_sha256") != profile["deployment_sha256"] or attestation.get("audit_digest") != digest:
                    raise ValueError("Runtime differs from independently audited deployment")
                adopted = {}
                completed_rounds = attestation.get("completed_rounds",[])
                if not isinstance(completed_rounds,list) or len(completed_rounds) > 1000:
                    raise ValueError("Bounded completed-round source readback required")
                from app.ml.federated_adoption import adopt_candidate
                for candidate_round in pending:
                    if candidate_round not in completed_rounds or not re.fullmatch(r'[a-f0-9]{64}',candidate_round):
                        continue
                    async with runtime.stream('GET',url.rstrip('/')+'/v1/rounds/'+candidate_round+'/candidate/'+org_id) as candidate_response:
                        candidate_response.raise_for_status()
                        encoded = bytearray()
                        async for chunk in candidate_response.aiter_bytes():
                            encoded.extend(chunk)
                            if len(encoded) > 16384:
                                raise ValueError('Aggregate candidate exceeds bounded contract')
                    candidate = json.loads(encoded)
                    if not isinstance(candidate,dict):
                        raise ValueError('Aggregate candidate object required')
                    adopted[candidate_round] = await adopt_candidate(org_id,candidate_round,candidate,settings,client)
                if attestation.get("in_progress") is True:
                    return {"status": "already_running", "adoption":adopted}
                # Do not consume another privacy round while the current
                # cohort is still collecting/evaluating its independent data.
                cohort_pending = any(
                    item.get('audit_digest') == digest and item.get('state') not in terminal
                    and datetime.now(timezone.utc)-timestamp(item.get('captured_at')) < MAX_ADOPTION_AGE
                    for row in rows.data or []
                    if row.get('id') in participants
                    for key,raw in safe_normalize_stored_dict(safe_normalize_stored_dict(row.get('settings')).get(LEDGER)).items()
                    if key in completed_rounds
                    if (item := safe_normalize_stored_dict(raw)))
                if cohort_pending:
                    return {"status":"awaiting_candidate_adoption","adoption":adopted}
                if len(participants) < 100:
                    return {"status":"dormant","reason":"100_current_distinct_tenant_approvals_required","adoption":adopted}
                completed = attestation.get("reserved_rounds")
                if type(completed) is not int or not 0 <= completed < profile["max_rounds"]:
                    return {"status": "dormant", "reason": "privacy_round_budget_exhausted_or_unverified"}
                # Recheck consent immediately before each dispatch. The runtime
                # must independently enforce it at client enrollment and again
                # before releasing the aggregate, as covered by its audit.
                for tenant in participants:
                    latest = await asyncio.to_thread(load_training_consents, tenant, settings)
                    record = safe_normalize_stored_dict(latest.get(self.catalog_name))
                    if not consent_is_approved(latest, self.catalog_name) or record.get("audit_digest") != digest:
                        return {"status": "dormant", "reason": "participant_permission_changed"}
                round_id = hashlib.sha256(f"{digest}:{completed + 1}".encode()).hexdigest()
                from app.ml.federated_projection import prepare_contributions
                contributions = await prepare_contributions(participants,round_id,profile,digest,settings)
                participants = sorted(contributions)
                # Claim permanently before dispatch. A timeout is uncertain and
                # requires runtime readback; never repeat a round blindly.
                claim = await asyncio.to_thread(redis.set, f"ml:federated-round:{round_id}", "dispatched", nx=True)
                if not claim:
                    previous = await runtime.get(url.rstrip('/')+'/v1/rounds/'+round_id)
                    if previous.status_code == 200:
                        previous.raise_for_status()
                        state = previous.json()
                        return {"status":state.get('state','reconciliation_required'),"round_id":round_id,"model_promoted":False}
                    if previous.status_code != 404:
                        return {"status":"reconciliation_required","round_id":round_id}
                    # Readback confirms no recorded dispatch. The remote
                    # database's round-id uniqueness also protects a late POST.
                    await asyncio.to_thread(redis.delete,f"ml:federated-round:{round_id}")
                    if not await asyncio.to_thread(redis.set,f"ml:federated-round:{round_id}","dispatched",nx=True):
                        return {"status":"already_running","round_id":round_id}
                response = await runtime.post(url.rstrip("/") + "/v1/rounds", headers={"Idempotency-Key": round_id},
                    json={"round_id": round_id, "program_id": profile["program_id"], "audit_digest": digest,
                          "participants": participants, "feature_schema_sha256": profile["feature_schema_sha256"],
                          "sealed_contributions": contributions})
                response.raise_for_status()
                result = response.json()
                if result.get("round_id") != round_id or result.get("state") not in {"accepted", "running", "completed"}:
                    raise ValueError("Runtime did not confirm the requested federation round")
                return {"status": result["state"], "round_id": round_id, "participants": len(participants),
                        "audit_digest": digest, "model_promoted": False}
        finally:
            try:
                await asyncio.to_thread(lock.release)
            except Exception:
                from app.core.logging import get_logger
                get_logger(__name__).warning("federation_coordination_lease_release_failed")
