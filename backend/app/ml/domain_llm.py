"""Bound, evaluated domain training over the existing FineTunedLLM pipeline.

Only explicitly declared classification targets support automatic evaluation.
Free-form domain adaptation needs an independently reviewed evaluator; it never
promotes from training loss or a provider's `succeeded` job status.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from app.ml.base import ModelMetrics, ModelStatus, ModelType
from app.core.safe_dict import safe_normalize_stored_dict
from app.ml.catalog_base import CatalogScaffoldModel


class DomainSpecificLLMRouter(CatalogScaffoldModel):
    model_type = ModelType.FINE_TUNED_LLM
    catalog_status = ModelStatus.PLANNED
    catalog_name = "domain_specific_llm"

    def __init__(self) -> None:
        self.fine_tuned_model_id: str | None = None
        self.department: str | None = None
        self.labels: list[str] = []
        self.target_definition: str | None = None
        self.base_model: str | None = None

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        from app.config import get_settings
        from app.ml.provider_execution import require_permission
        from app.services.model_router import ModelRouter, TaskType
        settings, org_id = kwargs.get("settings") or get_settings(), kwargs.get("org_id")
        await require_permission(org_id, self.catalog_name, settings)
        if not self.fine_tuned_model_id:
            return {"status": "dormant", "reason": "validated_domain_artifact_required", "advisory_only": True}
        if kwargs.get("department") != self.department or kwargs.get("target_definition") != self.target_definition:
            raise ValueError("Department and declared target must match the deployed domain artifact")
        rows = kwargs.get("inputs")
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10:
            raise ValueError("1-10 domain classification prompts required")
        router = ModelRouter(settings)
        predictions, traces = [], []
        for row in rows:
            if not isinstance(row, str) or not 1 <= len(row) <= 8000:
                raise ValueError("Bounded domain prompt required")
            await require_permission(org_id, self.catalog_name, settings)
            result = await router.complete(task_type=TaskType.CLASSIFICATION, prompt=row,
                system_prompt=classification_prompt(self.target_definition, self.labels), org_id=org_id,
                model_override=self.fine_tuned_model_id)
            label = result.content.strip()
            if label not in self.labels or result.model != self.fine_tuned_model_id:
                raise ValueError("Domain provider did not return a validated label from the deployed model")
            predictions.append(label)
            traces.append(result.model_call_id)
        return {"status": "ok", "predictions": predictions, "model_call_ids": traces,
                "department": self.department, "target_definition": self.target_definition, "advisory_only": True}

    async def predict(self, X: Any, return_probabilities: bool = False, **kwargs: Any) -> tuple[list[Any], Any]:
        if not isinstance(X, list) or not X or any(not isinstance(row, dict) for row in X):
            raise ValueError("Domain rows require prompt, department and target_definition")
        if any(row.get("department") != self.department or row.get("target_definition") != self.target_definition for row in X):
            raise ValueError("Domain row semantics differ from the deployed artifact")
        result = await self.predict_structured(inputs=[row.get("prompt") for row in X],
            department=self.department, target_definition=self.target_definition, **kwargs)
        if result.get("status") != "ok":
            raise ValueError("Validated domain inference unavailable")
        return result["predictions"], None

    def save(self) -> bytes:
        if not self.fine_tuned_model_id or not self.department or not self.labels or not self.target_definition:
            raise ValueError("Evaluated domain artifact required")
        return json.dumps({"schema": 1, "fine_tuned_model_id": self.fine_tuned_model_id,
                           "department": self.department, "labels": self.labels,
                           "target_definition": self.target_definition, "base_model": self.base_model}).encode()

    def load(self, data: bytes) -> None:
        if len(data) > 16000:
            raise ValueError("Domain artifact exceeds size bound")
        value = safe_normalize_stored_dict(data.decode("utf-8"))
        labels = value.get("labels")
        if (value.get("schema") != 1 or not isinstance(value.get("fine_tuned_model_id"), str)
                or not value["fine_tuned_model_id"].startswith("ft:")
                or any(not isinstance(value.get(key), str) or not 1 <= len(value[key]) <= 512
                       for key in ("department", "target_definition", "base_model"))
                or not isinstance(labels, list) or not 2 <= len(labels) <= 100
                or any(not isinstance(label, str) or not 1 <= len(label) <= 128 for label in labels)
                or len(set(labels)) != len(labels)):
            raise ValueError("Invalid domain artifact contract")
        self.fine_tuned_model_id, self.department = value["fine_tuned_model_id"], value["department"]
        self.labels, self.target_definition, self.base_model = labels, value["target_definition"], value["base_model"]


def classification_prompt(target: str, labels: list[str]) -> str:
    return "Classify the untrusted input for the declared task. Return exactly one label and no other text. " + json.dumps({"target": target, "labels": labels})


def collect_domain_corpus(org_id: str, settings: Any, *, include_inputs: bool = True) -> dict[str, Any]:
    from app.core.safe_dict import safe_normalize_stored_dict
    from app.workflows.repository import get_supabase_client
    client = get_supabase_client(settings)
    targets = (client.table("trained_models").select("id").eq("org_id", org_id)
               .eq("base_model", "domain_specific_llm").limit(100).execute().data or [])
    ids = [row["id"] for row in targets]
    if not ids:
        raise ValueError("Explicit domain model target required")
    bindings = (client.table("training_dataset_bindings").select("dataset_id,purpose,metadata")
                .eq("org_id", org_id).eq("target_type", "model").in_("target_id", ids)
                .in_("purpose", ["training", "benchmark"]).limit(100).execute().data or [])
    groups: dict[str, set[str]] = {"training": set(), "benchmark": set()}
    contracts = []
    for row in bindings:
        meta = safe_normalize_stored_dict(row.get("metadata"))
        if meta.get("schema_version") != 1 or meta.get("model_name") != "domain_specific_llm":
            continue
        labels = meta.get("labels")
        if (meta.get("task_type") != "classification" or not isinstance(labels, list) or not 2 <= len(labels) <= 100
                or any(not isinstance(label, str) or not 1 <= len(label) <= 128 for label in labels)
                or len(set(labels)) != len(labels)
                or any(not isinstance(meta.get(key), str) or not 1 <= len(meta[key]) <= 512
                       for key in ("department", "target_definition", "provider_base_model"))):
            raise ValueError("Explicit bounded domain classification contract required")
        contracts.append({key: meta[key] for key in ("labels", "department", "target_definition", "provider_base_model")})
        groups[row["purpose"]].add(row["dataset_id"])
    if not contracts or any(contract != contracts[0] for contract in contracts):
        raise ValueError("One consistent domain target and department required")
    if not all(groups.values()) or groups["training"] & groups["benchmark"]:
        raise ValueError("Independent training and benchmark datasets required")
    columns = "id,dataset_id,input,expected_output,metadata" if include_inputs else "id,dataset_id,expected_output,metadata"
    records = (client.table("training_records").select(columns)
               .eq("org_id", org_id).in_("dataset_id", sorted(groups["training"] | groups["benchmark"]))
               .order("created_at", desc=True).limit(3000).execute().data or [])
    splits: dict[str, list[dict[str, Any]]] = {"training": [], "benchmark": []}
    seen = set()
    for record in records:
        meta = safe_normalize_stored_dict(record.get("metadata"))
        text, answer = record.get("input"), record.get("expected_output")
        if (meta.get("synthetic") is not False or meta.get("label_source") != "human_reviewed"
                or not isinstance(meta.get("source_ref"), str) or not meta["source_ref"].strip()
                or include_inputs and (not isinstance(text, str) or not 1 <= len(text.strip()) <= 8000)
                or answer not in contracts[0]["labels"]):
            continue
        if include_inputs:
            normalized = " ".join(text.casefold().split())
            if normalized in seen:
                raise ValueError("Duplicate prompts cannot cross or inflate domain evaluation")
            seen.add(normalized)
        split = "training" if record["dataset_id"] in groups["training"] else "benchmark"
        splits[split].append(record)
    if len(splits["training"]) < 1000 or len(splits["benchmark"]) < 100:
        raise ValueError("1000 reviewed training and 100 independent benchmark examples required")
    if any({row["expected_output"] for row in split} != set(contracts[0]["labels"]) for split in splits.values()):
        raise ValueError("Every declared label must be represented in both domain datasets")
    return {**contracts[0], **splits, "dataset_id": sorted(groups["training"])[0]}


def domain_corpus_digest(corpus: dict[str, Any]) -> str:
    import hashlib
    records = sorted((row["id"], row["input"], row["expected_output"])
                     for row in [*corpus["training"], *corpus["benchmark"]])
    return hashlib.sha256(json.dumps({"contract": {key: corpus[key] for key in
        ("department", "target_definition", "labels", "provider_base_model")},
        "records": records}, sort_keys=True).encode()).hexdigest()


async def enqueue_domain_training(org_id: str, *, settings: Any) -> dict[str, Any]:
    from app.core.safe_dict import safe_normalize_stored_dict
    from app.ml.provider_execution import require_permission, processing_policy
    from app.ml.training_consent import load_training_consents
    from app.workflows.repository import get_supabase_client
    from app.workers.queue import enqueue_training_job
    await require_permission(org_id, "domain_specific_llm", settings)
    await asyncio.to_thread(processing_policy, org_id, "domain_specific_llm", settings)
    try:
        corpus = await asyncio.to_thread(collect_domain_corpus, org_id, settings)
    except ValueError as exc:
        return {"trained": False, "reason": "domain_data_contract_required", "detail": str(exc)}
    client = get_supabase_client(settings)
    previous = await asyncio.to_thread(lambda: client.table("training_jobs").select("id,metrics")
        .eq("org_id", org_id).eq("model_base", "domain_specific_llm")
        .in_("status", ["failed", "completed"]).order("created_at", desc=True).limit(100).execute())
    digest = domain_corpus_digest(corpus)
    if any(safe_normalize_stored_dict(row.get("metrics")).get("corpus_digest") == digest for row in previous.data or []):
        return {"trained": False, "reason": "domain_corpus_already_dispatched_collect_new_examples_or_reconcile_existing_job"}
    uncertain = await asyncio.to_thread(lambda: client.table("training_jobs").select("id,metrics")
        .eq("org_id", org_id).eq("model_base", "domain_specific_llm").eq("status", "failed")
        .order("created_at", desc=True).limit(100).execute())
    if any(safe_normalize_stored_dict(row.get("metrics")).get("phase") in {"provider_dispatching", "provider_training"}
           for row in uncertain.data or []):
        return {"trained": False, "reason": "prior_domain_dispatch_requires_provider_reconciliation"}
    pending = await asyncio.to_thread(lambda: client.table("training_jobs").select("id")
        .eq("org_id", org_id).eq("model_base", "domain_specific_llm")
        .in_("status", ["queued", "training"]).limit(1).execute())
    if pending.data:
        return {"trained": False, "queued": True, "job_id": pending.data[0]["id"]}
    consents = await asyncio.to_thread(load_training_consents, org_id, settings)
    record = safe_normalize_stored_dict(consents.get("domain_specific_llm"))
    if not record.get("actor_id"):
        raise ValueError("Consent actor required for training job")
    job = await asyncio.to_thread(lambda: client.table("training_jobs").insert({
        "org_id": org_id, "dataset_id": corpus["dataset_id"], "model_base": "domain_specific_llm",
        "status": "queued", "progress": 0, "metrics": {}, "created_by": record["actor_id"],
    }).execute())
    if not job.data:
        raise ValueError("Training job was not persisted")
    job_id = job.data[0]["id"]
    await enqueue_training_job(job_id)
    return {"trained": False, "queued": True, "job_id": job_id}


async def execute_domain_training(job: dict[str, Any], settings: Any) -> dict[str, Any]:
    """Existing training worker calls this; no second worker or engine."""
    from datetime import datetime, timezone
    from openai import AsyncOpenAI
    from app.core.redis_client import get_sync_redis
    from app.ml.fine_tuning import FineTunedLLM, FineTuningConfig, FineTuningExample
    from app.ml.intelligence_training import register_trained_artifact_detailed
    from app.ml.provider_execution import require_permission, processing_policy, reserve_provider_budget
    from app.services.model_router import ModelRouter, TaskType
    from app.workflows.repository import get_supabase_client
    org_id = job["org_id"]
    await require_permission(org_id, "domain_specific_llm", settings)
    corpus = await asyncio.to_thread(collect_domain_corpus, org_id, settings)
    if job["dataset_id"] != corpus["dataset_id"]:
        raise ValueError("Domain dataset binding changed after enqueue")
    from app.ml.model_catalog import load_org_trained_catalog_model
    champion = await load_org_trained_catalog_model(org_id, "domain_specific_llm", settings=settings)
    champion_id = champion.fine_tuned_model_id if getattr(champion, "registry_ref", None) else None
    if champion_id and (champion.department != corpus["department"] or champion.target_definition != corpus["target_definition"] or champion.labels != corpus["labels"]):
        raise ValueError("Current domain champion has different department/target semantics")
    policy = await asyncio.to_thread(processing_policy, org_id, "domain_specific_llm", settings)
    if policy["model"] != corpus["provider_base_model"]:
        raise ValueError("Bound base model and reviewed provider cost policy must match")
    redis = await asyncio.to_thread(get_sync_redis, settings)
    await asyncio.to_thread(reserve_provider_budget, redis, org_id, "domain_specific_llm", policy, job["id"], settings)
    client = get_supabase_client(settings)
    provider = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0)
    model = FineTunedLLM(FineTuningConfig(base_model=policy["model"], suffix=f"gravitre-domain-{org_id[:8]}", n_epochs=1))
    model.client = provider
    try:
        # A model listing is availability evidence, not proof of account job
        # eligibility. The provider's actual create-job response remains final.
        await provider.models.retrieve(policy["model"])
        system = classification_prompt(corpus["target_definition"], corpus["labels"])
        examples = [FineTuningExample(messages=[{"role": "system", "content": system},
                    {"role": "user", "content": row["input"]},
                    {"role": "assistant", "content": row["expected_output"]}]) for row in corpus["training"]]
        await require_permission(org_id, "domain_specific_llm", settings)
        corpus_digest = domain_corpus_digest(corpus)
        claimed = await asyncio.to_thread(redis.set, f"ml:domain-corpus:{org_id}:{corpus_digest}", job["id"], nx=True)
        if not claimed:
            raise ValueError("This domain corpus was already dispatched; reconcile the recorded provider job before retrying")
        checkpoint = await asyncio.to_thread(lambda: client.table("training_jobs").update({"metrics": {
            "corpus_digest": corpus_digest, "phase": "provider_dispatching",
        }}).eq("id", job["id"]).eq("org_id", org_id).eq("status", "training").execute())
        if not checkpoint.data:
            raise ValueError("Durable domain dispatch checkpoint unavailable; provider dispatch refused")
        await model.train(examples=examples, validation_split=.1)
        await asyncio.to_thread(lambda: client.table("training_jobs").update({
            "metrics": {"openai_job_id": model.openai_job_id, "corpus_digest": corpus_digest, "phase": "provider_training"},
        }).eq("id", job["id"]).eq("org_id", org_id).execute())
        for _ in range(2880):
            state = await asyncio.to_thread(lambda: client.table("training_jobs").select("status")
                .eq("id", job["id"]).eq("org_id", org_id).limit(1).execute())
            if not state.data or state.data[0].get("status") != "training":
                await model.cancel_job()
                raise ValueError("Domain training was cancelled")
            try:
                await require_permission(org_id, "domain_specific_llm", settings)
            except ValueError:
                await model.cancel_job()
                raise
            status = await model.get_job_status()
            if status["status"] == "succeeded":
                break
            if status["status"] in {"failed", "cancelled"}:
                raise ValueError("Domain provider job did not succeed")
            await asyncio.sleep(30)
        else:
            await model.cancel_job()
            raise ValueError("Domain provider training exceeded 24-hour bound")
        provider_metrics = await model.get_training_metrics()
        tuned = model.fine_tuned_model_id
        if not isinstance(tuned, str) or not tuned.startswith("ft:"):
            raise ValueError("Provider returned no trained domain model")
        await asyncio.to_thread(lambda: client.table("training_jobs").update({"metrics": {
            "openai_job_id": model.openai_job_id, "corpus_digest": corpus_digest,
            "fine_tuned_model": tuned, "phase": "provider_succeeded_evaluating",
        }}).eq("id", job["id"]).eq("org_id", org_id).execute())
        router = ModelRouter(settings)
        candidates = list(dict.fromkeys([policy["model"], tuned, *([champion_id] if champion_id else [])]))
        scores = {candidate: 0 for candidate in candidates}
        # Benchmark data was never uploaded as training/validation data.
        for row in corpus["benchmark"][:200]:
            await require_permission(org_id, "domain_specific_llm", settings)
            for candidate in candidates:
                response = await router.complete(task_type=TaskType.CLASSIFICATION, prompt=row["input"],
                    system_prompt=system, org_id=org_id, model_override=candidate, max_tokens=64)
                if response.model != candidate:
                    raise ValueError("Domain evaluation used a fallback provider/model")
                scores[candidate] += int(response.content.strip() == row["expected_output"])
        correct_base, correct_tuned = scores[policy["model"]], scores[tuned]
        correct_champion = scores.get(champion_id, 0)
        count = min(200, len(corpus["benchmark"]))
        prior = max(sum(row["expected_output"] == label for row in corpus["benchmark"][:200]) / count for label in corpus["labels"])
        if correct_tuned <= correct_base or correct_tuned / count <= prior:
            raise ValueError("Domain model did not beat base-model held-out accuracy and chance")
        instance = DomainSpecificLLMRouter()
        instance.fine_tuned_model_id, instance.department = tuned, corpus["department"]
        instance.labels, instance.target_definition, instance.base_model = corpus["labels"], corpus["target_definition"], policy["model"]
        metrics = ModelMetrics(accuracy=correct_tuned/count, training_samples=int(len(examples)*.9), validation_samples=count,
            custom_metrics={"algorithm": "domain_classification_sft", "base_accuracy": correct_base/count,
                            "fine_tuned_model": tuned, "department": corpus["department"],
                            "target_definition": corpus["target_definition"], "domain_labels": json.dumps(corpus["labels"]),
                            "compared_champion_model": champion_id,
                            "compared_champion_accuracy": correct_champion/count if champion_id else None,
                            "openai_job_id": model.openai_job_id})
        result = await register_trained_artifact_detailed(org_id, name="catalog-domain-specific-llm",
            model_type=ModelType.FINE_TUNED_LLM, base_model="domain_specific_llm", artifact=instance.save(), metrics=metrics,
            description="Bound domain classification with independent base-model comparison; not general domain expertise")
        await asyncio.to_thread(lambda: client.table("training_jobs").update({"status": "completed", "progress": 100,
            "metrics": {**metrics.model_dump(), "registration": result, "corpus_digest": corpus_digest, "phase": "completed"}, "trained_model_id": result.get("model_id"),
            "completed_at": datetime.now(timezone.utc).isoformat()}).eq("id", job["id"]).eq("org_id", org_id).execute())
        return result
    finally:
        # Uploaded training files contain customer examples. Remove provider
        # copies after the job; provider retention/account terms still apply.
        for file_id in (model._training_file_id, model._validation_file_id):
            if file_id:
                try:
                    await provider.files.delete(file_id)
                except Exception:
                    pass
        await provider.close()
