"""Tenant-local adoption of private aggregate candidates in the existing registry.

Only observations captured after the source artifact snapshot can be holdout
data. No raw rows or evaluation values are sent to the federation runtime.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from app.core.safe_dict import safe_normalize_stored_dict
from app.ml.learning_to_rank import FEATURE_NAMES, RetrievalRanker, RETRIEVAL_RANKER_MODEL_NAME

LEDGER = "federated_adoption"
ALGORITHM = "federated_retrieval_adoption"
MAX_ADOPTION_AGE = timedelta(days=14)
TERMINAL = {"adopted","rejected","stale_champion","registered_not_promoted","expired"}
_feedback_tasks: set[asyncio.Task] = set()


def timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timezone-bearing observation time required")
    return parsed


def update_anchor(client: Any, org_id: str, round_id: str, transform):
    if not re.fullmatch(r"[a-f0-9]{64}", round_id):
        raise ValueError("Immutable round identity required")
    for _ in range(3):
        rows = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data
        if not rows:
            raise ValueError("Organization adoption ledger unavailable")
        raw = rows[0].get("settings")
        payload = safe_normalize_stored_dict(raw)
        original = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        ledger = safe_normalize_stored_dict(payload.get(LEDGER))
        previous = safe_normalize_stored_dict(ledger.get(round_id))
        result = transform(previous)
        if result == previous:
            return result
        if round_id not in ledger and len(ledger) >= 1000:
            raise ValueError("Bounded adoption ledger exhausted")
        ledger[round_id] = result
        payload[LEDGER] = ledger
        query = client.table("organizations").update({"settings": payload}).eq("id", org_id)
        query = query.is_("settings", "null") if raw is None else query.eq("settings", original)
        if query.execute().data:
            return result
    raise ValueError("Concurrent adoption update; refused")


def save_source_anchor(client, org_id, round_id, audit_digest, registry_ref, captured_at):
    def create(previous):
        if previous:
            if previous.get("audit_digest") != audit_digest or previous.get("champion") != registry_ref:
                raise ValueError("Cannot overwrite a round's source artifact snapshot")
            return previous
        return {"audit_digest": audit_digest, "champion": registry_ref,
                "captured_at": captured_at, "state": "awaiting_candidate"}
    return update_anchor(client, org_id, round_id, create)


async def pending_adoption(org_id,settings,client):
    """Do not invalidate a contributed champion by retraining it mid-holdout."""
    from app.ml.training_consent import training_is_approved
    if not await training_is_approved(org_id,"federated_learning",settings):
        return {}
    from app.ml.federated_learning import verified_privacy_profile
    try:
        _,digest = await asyncio.to_thread(verified_privacy_profile,settings)
        rows = await asyncio.to_thread(lambda:client.table('organizations').select('settings').eq('id',org_id).limit(1).execute().data or [])
        ledger = safe_normalize_stored_dict(safe_normalize_stored_dict(rows[0].get('settings')).get(LEDGER)) if rows else {}
        now = datetime.now(timezone.utc)
        return {key:item for key,raw in ledger.items()
            if (item := safe_normalize_stored_dict(raw)).get('audit_digest') == digest
            and item.get('state') not in TERMINAL and now-timestamp(item.get('captured_at')) < MAX_ADOPTION_AGE}
    except Exception:
        # Unknown program/ledger readiness never authorizes federation. Existing
        # local training remains governed by its separate current permission.
        return {}


async def wake_after_feedback(org_id,settings,client):
    """Wake the existing company-learning job when independent data is ready."""
    anchors = await pending_adoption(org_id,settings,client)
    if not anchors:
        return
    ready = False
    for anchor in anchors.values():
        if await asyncio.to_thread(independent_holdout,client,org_id,anchor) is not None:
            ready = True
            break
    if not ready:
        return
    from app.core.redis_client import get_sync_redis
    redis = await asyncio.to_thread(get_sync_redis,settings)
    if redis is None or not await asyncio.to_thread(redis.set,f'ml:federation-feedback:{org_id}','queued',nx=True,ex=60):
        return
    from app.temporal.starters import temporal_enabled, start_company_intelligence_workflow
    if temporal_enabled():
        await start_company_intelligence_workflow(org_id)
    else:
        from app.services.company_intelligence_orchestrator import run_company_intelligence_for_org_sync
        await asyncio.to_thread(run_company_intelligence_for_org_sync,org_id,settings)


def schedule_feedback_reconciliation(org_id,settings,client):
    async def guarded():
        try:
            await wake_after_feedback(org_id,settings,client)
        except Exception:
            from app.core.logging import get_logger
            get_logger(__name__).warning('federated_feedback_reconciliation_unavailable org_id=%s',org_id)
    task = asyncio.create_task(guarded())
    _feedback_tasks.add(task)
    task.add_done_callback(_feedback_tasks.discard)


async def artifact_permission(org_id: str, artifact: Any, settings: Any) -> bool:
    raw = getattr(artifact, "federation", None)
    if raw is None and getattr(artifact,"_ranker",None) is not None:
        raw = getattr(artifact._ranker,"federation",None)
    if raw is None:
        return True  # Existing local artifacts retain their existing permission.
    provenance = safe_normalize_stored_dict(raw)
    if not provenance:
        return False
    from app.ml.federated_learning import verified_privacy_profile
    from app.ml.training_consent import load_training_consents, consent_is_approved
    try:
        _, digest = await asyncio.to_thread(verified_privacy_profile, settings)
        consents = await asyncio.to_thread(load_training_consents, org_id, settings)
        record = safe_normalize_stored_dict(consents.get("federated_learning"))
        return (consent_is_approved(consents, "federated_learning")
                and record.get("audit_digest") == digest == provenance.get("audit_digest"))
    except Exception:
        return False


def candidate_ranker(parameters, round_id, audit_digest) -> RetrievalRanker:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from app.ml.source_reliability import clip_reliability_weight
    if not isinstance(parameters, list) or any(type(value) not in {int, float} for value in parameters):
        raise ValueError("Five finite aggregate parameters required")
    vector = np.asarray(parameters, dtype=float)
    if vector.shape != (5,) or not np.isfinite(vector).all():
        raise ValueError("Five finite aggregate parameters required")
    result = RetrievalRanker()
    result.model = LogisticRegression()
    result.model.classes_ = np.array([0, 1])
    result.model.coef_ = vector[:4].reshape(1, 4)
    result.model.intercept_ = vector[4:]
    result.model.n_features_in_ = 4
    result.model.n_iter_ = np.array([0])
    # Aggregation is in the canonical raw feature basis, so scaling is identity.
    result.scaler = StandardScaler()
    result.scaler.mean_, result.scaler.scale_, result.scaler.var_ = np.zeros(4), np.ones(4), np.ones(4)
    result.scaler.n_features_in_, result.scaler.n_samples_seen_ = 4, 0
    result.learned_reliability_weight = clip_reliability_weight(abs(vector[1]))
    result.federation = {"round_id": round_id, "audit_digest": audit_digest}
    return result


def independent_holdout(client, org_id, anchor):
    cutoff = timestamp(anchor["captured_at"])
    rows = (client.table("rag_chunk_outcomes")
            .select("id,message_id,ranker_features,ranker_features_observed_at,recorded_at,outcome_helpful")
            .eq("org_id", org_id).gt("ranker_features_observed_at", cutoff.isoformat())
            .not_.is_("outcome_helpful", "null").not_.is_("ranker_features", "null")
            .order("recorded_at").order("id").limit(1000).execute().data or [])
    selected, messages = [], set()
    for row in rows:
        features = safe_normalize_stored_dict(row.get("ranker_features"))
        try:
            observed, recorded = timestamp(row.get("ranker_features_observed_at")), timestamp(row.get("recorded_at"))
            if not cutoff < observed <= recorded <= datetime.now(timezone.utc):
                continue
            if set(features) != set(FEATURE_NAMES) or any(type(features[key]) not in {int,float} or not math.isfinite(features[key]) for key in FEATURE_NAMES):
                continue
            if type(row.get("outcome_helpful")) is not bool or not row.get("id") or not row.get("message_id"):
                continue
            # Multiple chunks receiving the same message feedback are not
            # independent labels. Count each message once, in source order.
            if row["message_id"] in messages:
                continue
            messages.add(row["message_id"])
            selected.append({"id": row["id"], "features": features, "label": int(row["outcome_helpful"])})
            if len(selected) == 100:
                break
        except (ValueError, TypeError):
            continue
    if len(selected) < 100:
        return None
    if min(sum(row["label"] == label for row in selected) for label in (0,1)) < 10:
        return None
    digest = hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return selected, digest


def evaluate(candidate, champion, holdout, digest, round_id, champion_ref):
    from sklearn.metrics import accuracy_score, roc_auc_score, log_loss
    from app.ml.base import ModelMetrics
    matrix = np.array([[row["features"][key] for key in FEATURE_NAMES] for row in holdout])
    labels = np.array([row["label"] for row in holdout])
    predicted = candidate.model.predict_proba(candidate.scaler.transform(matrix))[:,1]
    previous = champion.model.predict_proba(champion.scaler.transform(matrix))[:,1]
    prior = np.full(len(labels), labels.mean())
    loss, old_loss, prior_loss = (float(log_loss(labels, scores, labels=[0,1])) for scores in (predicted,previous,prior))
    accuracy, old_accuracy = (float(accuracy_score(labels, scores >= .5)) for scores in (predicted,previous))
    auc, old_auc = (float(roc_auc_score(labels,scores)) for scores in (predicted,previous))
    return ModelMetrics(accuracy=accuracy, auc_roc=auc, validation_loss=loss, training_samples=0, validation_samples=len(labels),
        custom_metrics={"algorithm": ALGORITHM, "federated_round": round_id, "holdout_digest": digest,
            "federated_audit_digest":candidate.federation["audit_digest"],
            "compared_champion_model": champion_ref["model_id"], "compared_champion_version": champion_ref["version"],
            "compared_champion_accuracy": old_accuracy, "compared_champion_auc": old_auc,
            "compared_champion_loss": old_loss, "prior_loss": prior_loss})


def promotion_decision(metrics):
    custom = safe_normalize_stored_dict(metrics.get("custom_metrics"))
    keys = ("accuracy","auc_roc","validation_loss")
    others = ("compared_champion_accuracy","compared_champion_auc","compared_champion_loss","prior_loss")
    values = [metrics.get(key) for key in keys]+[custom.get(key) for key in others]
    if (any(type(value) not in {int,float} or not math.isfinite(value) for value in values)
            or type(metrics.get("validation_samples")) is not int or metrics["validation_samples"] < 100
            or not re.fullmatch(r"[a-f0-9]{64}",str(custom.get("holdout_digest","")))
            or not re.fullmatch(r"[a-f0-9]{64}",str(custom.get("federated_round","")))
            or not re.fullmatch(r"[a-f0-9]{64}",str(custom.get("federated_audit_digest","")))
            or not custom.get("compared_champion_model") or type(custom.get("compared_champion_version")) is not int
            or custom["compared_champion_version"] < 1):
        return False, "federated_independent_holdout_required", {}
    accuracy, auc, loss, old_accuracy, old_auc, old_loss, prior_loss = values
    wins = (0 <= accuracy <= 1 and .5 < auc <= 1 and 0 <= old_accuracy <= 1 and 0 <= old_auc <= 1
            and old_loss >= 0 and prior_loss > 0 and accuracy >= old_accuracy and auc >= old_auc
            and 0 <= loss < min(old_loss,prior_loss)-1e-8)
    return wins, "federated_same_holdout_pass" if wins else "federated_same_holdout_rejected", {"validation_samples":metrics["validation_samples"],"holdout_digest":custom["holdout_digest"]}


async def adopt_candidate(org_id, round_id, candidate, settings, client):
    from app.ml.training_consent import training_is_approved
    from app.ml.federated_learning import verified_privacy_profile
    from app.ml.model_catalog import load_org_trained_catalog_model
    from app.ml.intelligence_training import register_trained_artifact_detailed
    from app.ml.base import ModelType
    from app.ml.registry import get_model_registry
    _, audit = await asyncio.to_thread(verified_privacy_profile,settings)
    for name in ("federated_learning","retrieval_ranker"):
        if not await training_is_approved(org_id,name,settings):
            return {"state":"permission_required"}
    from types import SimpleNamespace
    if not await artifact_permission(org_id,SimpleNamespace(federation={"audit_digest":audit}),settings):
        return {"state":"permission_required"}
    anchor = await asyncio.to_thread(update_anchor,client,org_id,round_id,lambda current:current)
    if not anchor or anchor.get("audit_digest") != audit:
        return {"state":"source_snapshot_required"}
    if anchor.get("state") in TERMINAL:
        return {"state":anchor["state"]}
    if datetime.now(timezone.utc)-timestamp(anchor.get('captured_at')) >= MAX_ADOPTION_AGE:
        await asyncio.to_thread(update_anchor,client,org_id,round_id,lambda current:{**current,'state':'expired'})
        return {'state':'expired'}
    from app.ml.federated_runtime.privacy import feature_schema_digest
    if (candidate.get("schema") != 1 or candidate.get("round_id") != round_id or candidate.get("audit_digest") != audit
            or candidate.get("feature_schema_sha256") != feature_schema_digest()):
        raise ValueError("Candidate round/audit/features differ from source snapshot")
    candidate_digest = hashlib.sha256(json.dumps(candidate,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    if anchor.get("candidate_digest") and anchor["candidate_digest"] != candidate_digest:
        raise ValueError("A round cannot change its aggregate candidate")
    ref = safe_normalize_stored_dict(anchor.get("champion"))
    registry = get_model_registry()
    # Reconcile a prior uncertain registration from the durable source before
    # any attempt to add another version or spend storage again.
    if anchor.get("state") == "registering":
        versions = await asyncio.to_thread(lambda: client.table("model_versions").select("version,metrics")
            .eq("model_id",ref["model_id"]).order("version",desc=True).limit(1000).execute().data or [])
        existing = next((row for row in versions if safe_normalize_stored_dict(safe_normalize_stored_dict(row.get("metrics")).get("custom_metrics")).get("federated_round") == round_id),None)
        if existing:
            model = await registry.get_model(ref["model_id"])
            state = "registered_not_promoted"
            if model and model.org_id == org_id and model.deployed_version == existing["version"]:
                restored = RetrievalRanker()
                restored.load(await registry.load_model_artifact(ref["model_id"], existing["version"]))
                if (restored.federation != {"round_id": round_id, "audit_digest": audit}
                        or not await artifact_permission(org_id, restored, settings)):
                    return {"state": "registration_reconciliation_required"}
                state = "adopted"
            await asyncio.to_thread(update_anchor,client,org_id,round_id,lambda current:{**current,"state":state,"version":existing["version"]})
            return {"state":state,"version":existing["version"]}
        return {"state":"registration_reconciliation_required"}
    champion = await load_org_trained_catalog_model(org_id,"retrieval_ranker",settings=settings)
    if getattr(champion,"registry_ref",None) != ref:
        await asyncio.to_thread(update_anchor,client,org_id,round_id,lambda current:{**current,"state":"stale_champion"})
        return {"state":"stale_champion"}
    heldout = await asyncio.to_thread(independent_holdout,client,org_id,anchor)
    if heldout is None:
        return {"state":"awaiting_independent_outcomes"}
    rows,digest = heldout
    if anchor.get("holdout_digest") and anchor["holdout_digest"] != digest:
        raise ValueError("Frozen holdout changed; adoption cannot silently select another benchmark")
    ranker = candidate_ranker(candidate.get("parameters"),round_id,audit)
    metrics = await asyncio.to_thread(evaluate,ranker,champion,rows,digest,round_id,ref)
    accepted,reason,_ = promotion_decision(metrics.model_dump())
    state = "registering" if accepted else "rejected"
    def claim(current):
        if current != anchor:
            raise ValueError("Concurrent candidate adoption; reconciliation required")
        return {**current,"state":state,"candidate_digest":candidate_digest,"holdout_digest":digest,"reason":reason}
    await asyncio.to_thread(update_anchor,client,org_id,round_id,claim)
    if not accepted:
        return {"state":state,"reason":reason}
    registration = await register_trained_artifact_detailed(org_id,name=RETRIEVAL_RANKER_MODEL_NAME,
        model_type=ModelType.CLASSIFIER,base_model="retrieval_ranker",artifact=ranker.save(),metrics=metrics,
        description="Private aggregate evaluated on independent tenant-local retrieval feedback")
    state = "adopted" if registration.get("deployed") else "registered_not_promoted"
    await asyncio.to_thread(update_anchor,client,org_id,round_id,lambda current:{**current,"state":state,"version":registration.get("version"),"reason":registration.get("reason")})
    return {"state":state,"registration":registration}
