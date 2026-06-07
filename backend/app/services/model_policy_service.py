"""Org model allowlist / blocklist policy (STA-90)."""
from __future__ import annotations

from typing import Any, Literal

from app.services.ai_guardrails import AIModelPolicyError

PolicyMode = Literal["open", "allowlist", "blocklist"]

DEFAULT_MODEL_POLICY: dict[str, Any] = {
    "mode": "open",
    "providers": [],
    "models": [],
}


def normalize_model_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_MODEL_POLICY)
    mode = str(raw.get("mode") or "open").strip().lower()
    if mode not in {"open", "allowlist", "blocklist"}:
        mode = "open"
    providers = [str(p).strip().lower() for p in (raw.get("providers") or []) if str(p).strip()]
    models = [str(m).strip() for m in (raw.get("models") or []) if str(m).strip()]
    return {"mode": mode, "providers": providers, "models": models}


def load_org_model_policy(client: Any, org_id: str) -> dict[str, Any]:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (row.data or [{}])[0].get("settings") if row.data else {}
    if not isinstance(settings, dict):
        settings = {}
    policy = settings.get("modelPolicy") or settings.get("model_policy")
    return normalize_model_policy(policy if isinstance(policy, dict) else None)


def save_org_model_policy(client: Any, org_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_model_policy(policy)
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute()
    settings = (row.data or [{}])[0].get("settings") if row.data else {}
    if not isinstance(settings, dict):
        settings = {}
    settings = {**settings, "modelPolicy": normalized}
    client.table("organizations").update({"settings": settings}).eq("id", org_id).execute()
    return normalized


def assert_model_allowed(policy: dict[str, Any], *, provider: str, model: str) -> None:
    """Raise AIModelPolicyError when provider/model violates org policy."""
    normalized = normalize_model_policy(policy)
    mode = normalized["mode"]
    if mode == "open":
        return

    provider_key = provider.strip().lower()
    model_key = model.strip()
    allowed_providers = set(normalized["providers"])
    allowed_models = set(normalized["models"])

    if mode == "allowlist":
        provider_ok = not allowed_providers or provider_key in allowed_providers
        model_ok = not allowed_models or model_key in allowed_models
        if allowed_providers and allowed_models:
            if not (provider_ok and model_ok):
                raise AIModelPolicyError(provider=provider_key, model=model_key, mode=mode)
        elif allowed_providers and not provider_ok:
            raise AIModelPolicyError(provider=provider_key, model=model_key, mode=mode)
        elif allowed_models and not model_ok:
            raise AIModelPolicyError(provider=provider_key, model=model_key, mode=mode)
        return

    if mode == "blocklist":
        if provider_key in allowed_providers or model_key in allowed_models:
            raise AIModelPolicyError(provider=provider_key, model=model_key, mode=mode)
