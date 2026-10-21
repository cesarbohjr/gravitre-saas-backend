"""Governed image generation through the existing tool and artifact paths."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from typing import Any
from uuid import UUID


from app.ml.base import ModelStatus, ModelType
from app.core.safe_dict import safe_normalize_stored_dict
from app.ml.catalog_base import CatalogScaffoldModel


class DiffusionModelConnector(CatalogScaffoldModel):
    # Catalog identity is retained for compatibility; the configured provider
    # need not use a diffusion architecture. No second image engine is created.
    model_type = ModelType.FINE_TUNED_LLM
    catalog_status = ModelStatus.PLANNED
    catalog_name = "diffusion_model"

    async def predict_structured(self, **kwargs: Any) -> dict[str, Any]:
        # Image generation is a paid side effect, never advisory inference.
        return {"status": "dormant", "reason": "governed_generation_tool_required", "advisory_only": True}

    async def generate(self, *, org_id: str, actor_id: str, prompt: str, operation_id: str, settings: Any) -> dict[str, Any]:
        from openai import AsyncOpenAI
        from app.core.redis_client import get_sync_redis
        from app.ml.provider_execution import processing_policy, require_permission, reserve_provider_budget, private_artifact_storage
        from app.services.ai_guardrails import moderate_input, redact_pii
        from app.services.byo_storage import put_org_file, resolve_download_url, read_org_file
        from app.workflows.repository import get_supabase_client
        if not actor_id or not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 8000:
            raise ValueError("Authenticated actor and bounded generation prompt required")
        operation_id = str(UUID(operation_id))
        await require_permission(org_id, self.catalog_name, settings)
        policy = await asyncio.to_thread(processing_policy, org_id, self.catalog_name, settings)
        if not policy["model"].startswith("gpt-image-"):
            raise ValueError("Configured image-generation model required")
        redis = await asyncio.to_thread(get_sync_redis, settings)
        if redis is None:
            raise ValueError("Generation coordination unavailable")
        prompt = redact_pii(prompt)
        fingerprint = hashlib.sha256((actor_id + "\0" + prompt + "\0" + policy["model"]).encode()).hexdigest()
        key = f"ml:image:{org_id}:{operation_id}"
        claimed = await asyncio.to_thread(redis.set, key, json.dumps({"state": "started", "fingerprint": fingerprint}), nx=True)
        if not claimed:
            stored = safe_normalize_stored_dict(await asyncio.to_thread(redis.get, key))
            if stored.get("fingerprint") != fingerprint:
                raise ValueError("Operation id was already used for different inputs")
            if stored.get("state") == "complete":
                result = stored["result"]
                client = get_supabase_client(settings)
                path = f"{org_id}/generated-images/{operation_id}.png"
                data = await asyncio.to_thread(read_org_file, client, settings, org_id=org_id,
                    logical_bucket=settings.chat_artifacts_bucket, path=path, max_bytes=20*1024*1024)
                if hashlib.sha256(data).hexdigest() != result.get("sha256"):
                    raise ValueError("Stored image no longer matches the verified generation")
                download = await asyncio.to_thread(resolve_download_url, client, settings, org_id=org_id,
                    logical_bucket=settings.chat_artifacts_bucket, path=path, ttl=300)
                return {**result, "hostedFiles": [{**item, "download_url": download.get("url")}
                                                 for item in result.get("hostedFiles", [])]}
            return {"status": "outcome_uncertain", "reason": "Do not retry generation with a new operation id; reconcile this operation first."}
        # Keep the claim even on failure: dispatch timeouts/crashes may still
        # incur provider charges. Never blindly retry a paid generation.
        await asyncio.to_thread(reserve_provider_budget, redis, org_id, self.catalog_name, policy, operation_id, settings)
        client = get_supabase_client(settings)
        bucket = settings.chat_artifacts_bucket
        destination = await asyncio.to_thread(private_artifact_storage, client, settings, org_id)
        provider = AsyncOpenAI(api_key=settings.openai_api_key, max_retries=0, timeout=120)
        try:
            await moderate_input(prompt, settings, provider)
            await require_permission(org_id, self.catalog_name, settings)
            try:
                response = await provider.images.generate(model=policy["model"], prompt=prompt, n=1,
                                                           size="1024x1024", quality="low", output_format="png")
            except Exception as exc:
                raise ValueError(f"Image provider dispatch unconfirmed ({type(exc).__name__}); reconcile the operation before retrying") from None
            encoded = response.data[0].b64_json if response.data else None
            if not isinstance(encoded, str) or len(encoded) > 28_000_000:
                raise ValueError("Generation returned no bounded image")
            raw = base64.b64decode(encoded, validate=True)
            from app.ml.media_inputs import reencode_image
            if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Generated PNG container required')
            data = await asyncio.to_thread(reencode_image,raw,output_format='png',expected_size=(1024,1024))
            path = f"{org_id}/generated-images/{operation_id}.png"
            await asyncio.to_thread(put_org_file, client, settings, org_id=org_id, logical_bucket=bucket,
                                    path=path, data=data, content_type="image/png", purpose="generated_image", upsert=False, expected_storage=destination)
            readback = await asyncio.to_thread(read_org_file, client, settings, org_id=org_id,
                                               logical_bucket=bucket, path=path, max_bytes=20*1024*1024)
            digest = hashlib.sha256(data).hexdigest()
            if hashlib.sha256(readback).hexdigest() != digest:
                raise ValueError("Generated artifact readback mismatch")
            download = await asyncio.to_thread(resolve_download_url, client, settings, org_id=org_id,
                                               logical_bucket=bucket, path=path, ttl=300)
            result = {"status": "ok", "operation_id": operation_id, "model": policy["model"],
                      "artifact_verified": True, "sha256": digest, "storage_path": path,
                      "hostedFiles": [{"id": operation_id, "filename": "generated-image.png", "mime_type": "image/png",
                                       "byte_size": len(data), "download_url": download.get("url"), "durable": True}],
                      "cost_evidence": "reserved_reviewed_upper_bound_not_actual_charge"}
            await asyncio.to_thread(redis.set, key, json.dumps({"state": "complete", "fingerprint": fingerprint, "result": result}))
            return result
        finally:
            await provider.close()
