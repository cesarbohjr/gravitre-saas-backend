"""Explicitly authorized sandbox provider write/readback verification.

No default vendor, URL, token or credentials. Never called by PR CI. Operator
supplies a dedicated nonproduction HTTPS endpoint implementing:
POST /actions -> {"id": "...", "idempotency_key": "..."}
GET /actions/<id> -> {"id": "...", "idempotency_key": "...", "status": "applied"}
The readback must be from the provider's authoritative resource API, not from
the write response or a Gravitre-side cache.

This generic adapter must be mapped and reviewed against a concrete provider
before it represents provider-specific acceptance evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4


def _request(url: str, *, token: str, method: str, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    # No redirects into other hosts or provider regions: verify each final URL.
    class DenyRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("sandbox verification redirects are prohibited")

    opener = urllib.request.build_opener(DenyRedirect)
    with opener.open(req, timeout=15) as response:
        body = response.read(32768)
        if response.read(1):
            raise RuntimeError("provider response exceeds maximum size")
        return json.loads(body)


def verify(*, base: str, allowed_host: str, token: str, approved: bool):
    from urllib.parse import urlsplit, quote
    parts = urlsplit(base)
    if not approved:
        raise RuntimeError("explicit sandbox operator approval required")
    if parts.scheme != "https" or not parts.hostname or parts.hostname != allowed_host:
        raise RuntimeError("sandbox HTTPS host is not exactly allowlisted")
    if parts.username or parts.password or parts.query or parts.fragment or parts.port not in (None, 443):
        raise RuntimeError("unsafe sandbox URL")
    if not token or token.startswith("sk-test") or len(token) < 12:
        raise RuntimeError("sandbox token not configured")
    prefix = base.rstrip("/")
    action_key = f"qa-p27-{uuid4()}"
    # A harmless dedicated synthetic resource only; do not use customer data.
    payload = {"idempotency_key": action_key, "test_marker": action_key,
               "mode": "synthetic-acceptance"}
    written = _request(prefix + "/actions", token=token, method="POST", payload=payload)
    provider_id = str(written.get("id") or "")
    if not provider_id or written.get("idempotency_key") != action_key:
        raise RuntimeError("write receipt lacks provider id or matching idempotency key")
    resource = _request(
        prefix + "/actions/" + quote(provider_id, safe=""),
        token=token, method="GET")
    if resource.get("id") != provider_id:
        raise RuntimeError("independent readback does not identify the created provider object")
    if resource.get("idempotency_key") != action_key:
        raise RuntimeError("independent readback does not match idempotency key")
    if resource.get("status") != "applied":
        raise RuntimeError("provider has not confirmed applied state")
    # Re-submit same operation key; authoritative provider must deduplicate.
    repeat = _request(prefix + "/actions", token=token, method="POST", payload=payload)
    if repeat.get("id") != provider_id:
        raise RuntimeError("same idempotency key created another provider resource")
    print(json.dumps({"result": "PASS", "mode": "SANDBOX_LIVE",
                      "provider_host": allowed_host, "provider_id": provider_id,
                      "idempotency_key": action_key,
                      "readback": "authoritative_resource",
                      "duplicate_write": False}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--approve-sandbox-write", action="store_true", required=True)
    args = parser.parse_args()
    base = os.environ.get("P27_SANDBOX_BASE_URL", "").strip()
    hostname = os.environ.get("P27_SANDBOX_ALLOWED_HOST", "").strip()
    token = os.environ.get("P27_SANDBOX_TOKEN", "")
    if not base or not hostname:
        raise SystemExit("BLOCKED: approved sandbox URL/host not configured")
    verify(base=base, allowed_host=hostname, token=token,
           approved=args.approve_sandbox_write)


if __name__ == "__main__":
    main()
