"""Bounded *real* Anthropic acceptance inference, with sanitized durable evidence.

Opt-in CI only. A key's presence is not authorization/credit verification.
Never print prompt, provider response, credential or a provider exception body.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"


def classify_http(status: int) -> str:
    if status == 401:
        return "unauthorized"
    if status == 402:
        return "insufficient_credits"
    if status == 403:
        return "permission_denied"
    if status == 404:
        return "model_not_found"
    if status == 429:
        return "rate_limited_or_quota"
    if status >= 500:
        return "provider_error"
    return "request_rejected"


def probe(*, key: str, model: str = DEFAULT_MODEL, timeout_s: int = 25) -> dict:
    """One small live model request. Does not echo generated text or server errors."""
    if not key.strip():
        return {"status": "BLOCKED", "category": "acceptance_credential_missing"}
    request = Request(
        ENDPOINT,
        data=json.dumps({
            "model": model,
            "max_tokens": 24,
            "temperature": 0,
            "messages": [
                {"role": "user", "content": "Reply with exactly READY, without anything else."}
            ],
        }).encode("utf-8"),
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_s) as response:
            status = response.status
            body = response.read(65536)
    except HTTPError as exc:
        # Never read/log the response body; it can contain account metadata.
        return {"status": "BLOCKED", "category": classify_http(exc.code), "http_status": exc.code}
    except (URLError, TimeoutError, OSError):
        return {"status": "BLOCKED", "category": "provider_transport_error"}
    if status != 200:
        return {"status": "BLOCKED", "category": classify_http(status), "http_status": status}
    try:
        payload = json.loads(body)
        chunks = payload.get("content") if isinstance(payload, dict) else None
        text = "".join(
            chunk.get("text", "") for chunk in (chunks or [])
            if isinstance(chunk, dict) and chunk.get("type") == "text"
        )
        valid = text.strip() == "READY"
    except (ValueError, TypeError, AttributeError):
        valid = False
    return {
        "status": "PASS" if valid else "BLOCKED",
        "category": "inference_verified" if valid else "unexpected_model_response",
        "http_status": 200,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="acceptance-results/anthropic-inference.json")
    args = parser.parse_args()
    model = os.getenv("ACCEPTANCE_ANTHROPIC_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    result = probe(key=os.getenv("ANTHROPIC_API_KEY", ""), model=model)
    evidence = {
        "source_sha": os.getenv("ACCEPTANCE_SOURCE_SHA", ""),
        "provider": "anthropic",
        "model": model,
        **result,
        "scope": "one paid live model request; not Pipecat/LiveKit quality certification",
        "certified": False,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
