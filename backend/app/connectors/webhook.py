"""IN-12: Webhook sender with SSRF protections. Approval-gated; no PII in logs."""
from __future__ import annotations

import hashlib
import http.client
import hmac
import ipaddress
import json
import socket
import time
import uuid
from typing import Any

import httpx

ALLOWED_HEADER_NAMES = {
    "x-event-type",
    "x-request-id",
    "x-gravitre-run-id",
    "content-type",
}

DEFAULT_ALLOWED_SCHEMES = ["https"]
DEFAULT_TIMEOUT_SEC = 5
MAX_TIMEOUT_SEC = 10
DEFAULT_MAX_PAYLOAD_BYTES = 65536
MAX_MAX_PAYLOAD_BYTES = 262144
DEFAULT_RETRY_COUNT = 1
MAX_RETRY_COUNT = 2
DEFAULT_BACKOFF_MS = 250
MAX_BACKOFF_MS = 1000


def _normalize_header_name(name: str) -> str:
    return (name or "").strip().lower()


def _header_name_from_secret_key(key_name: str) -> str:
    # WEBHOOK_HEADER_X_EVENT_TYPE -> X-Event-Type
    raw = key_name[len("WEBHOOK_HEADER_") :]
    return raw.replace("_", "-")


def payload_hash(payload_bytes: bytes) -> str:
    return hashlib.sha256(payload_bytes).hexdigest()


def validate_path(path: str) -> str:
    if not path or not isinstance(path, str):
        raise ValueError("Webhook path is required")
    if not path.startswith("/"):
        raise ValueError("Webhook path must start with '/'")
    lower = path.lower()
    if ".." in path or "%2e" in lower or "%2f" in lower or "\\\\" in path:
        raise ValueError("Webhook path contains invalid traversal")
    if "?" in path or "#" in path:
        raise ValueError("Webhook path must not include query or fragment")
    return path


def resolve_and_validate_host(host: str) -> list[str]:
    if not host or not isinstance(host, str):
        raise ValueError("Webhook host is required")
    if ":" in host:
        raise ValueError("Custom ports are not allowed")
    if host.lower().startswith("localhost"):
        raise ValueError("Webhook host not allowed")
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Webhook host resolution failed")
    ips: list[str] = []
    for info in infos:
        ip_str = info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if not ip.is_global:
            raise ValueError("Webhook target resolves to non-global address")
        ips.append(ip_str)
    if not ips:
        raise ValueError("No valid IPs resolved for host")
    return ips


def coerce_payload(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (dict, list)):
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        return raw.encode("utf-8")
    raise ValueError("Webhook payload must be object, list, string, or bytes")


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (headers or {}).items():
        name = _normalize_header_name(k)
        if name not in ALLOWED_HEADER_NAMES:
            raise ValueError(f"Header {k!r} not allowlisted")
        val = (v or "").strip()
        if len(val) > 256:
            raise ValueError(f"Header {k!r} value too long")
        out[k] = val
    if len(out) > 10:
        raise ValueError("Too many headers")
    return out


def build_headers(
    step_headers: dict[str, str] | None,
    secret_headers: dict[str, str] | None,
    bearer_token: str | None,
    hmac_secret: str | None,
    payload_bytes: bytes,
) -> tuple[dict[str, str], list[str], str]:
    headers: dict[str, str] = {}
    headers["Content-Type"] = "application/json"
    if step_headers:
        headers.update(sanitize_headers(step_headers))
    if secret_headers:
        headers.update(sanitize_headers(secret_headers))
    request_id = str(uuid.uuid4())
    headers.setdefault("X-Request-Id", request_id)
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    if hmac_secret:
        ts = str(int(time.time()))
        sign_base = ts.encode("utf-8") + b"." + payload_bytes
        sig = hmac.new(hmac_secret.encode("utf-8"), sign_base, hashlib.sha256).hexdigest()
        headers["X-Gravitre-Signature"] = f"sha256={sig}"
        headers["X-Gravitre-Timestamp"] = ts
    preview_keys = [k for k in headers.keys() if _normalize_header_name(k) in ALLOWED_HEADER_NAMES]
    return headers, preview_keys, request_id


def parse_connector_config(config: dict) -> dict[str, Any]:
    allowed_hosts = config.get("allowed_hosts") or []
    if not isinstance(allowed_hosts, list) or not allowed_hosts:
        raise ValueError("Connector allowed_hosts must be a non-empty list")
    allowed_hosts = [h.strip() for h in allowed_hosts if isinstance(h, str) and h.strip()]
    for host in allowed_hosts:
        if "/" in host or "?" in host or "#" in host:
            raise ValueError("allowed_hosts must be hostnames only (no path/query)")
    if not allowed_hosts:
        raise ValueError("Connector allowed_hosts must be a non-empty list")
    allowed_schemes = config.get("allowed_schemes") or DEFAULT_ALLOWED_SCHEMES
    if not isinstance(allowed_schemes, list):
        allowed_schemes = DEFAULT_ALLOWED_SCHEMES
    allowed_schemes = [s.strip().lower() for s in allowed_schemes if isinstance(s, str) and s.strip()]
    if not allowed_schemes:
        allowed_schemes = DEFAULT_ALLOWED_SCHEMES
    timeout = int(config.get("timeout_seconds", DEFAULT_TIMEOUT_SEC))
    timeout = max(1, min(timeout, MAX_TIMEOUT_SEC))
    max_payload = int(config.get("max_payload_bytes", DEFAULT_MAX_PAYLOAD_BYTES))
    max_payload = max(1024, min(max_payload, MAX_MAX_PAYLOAD_BYTES))
    retry_count = int(config.get("retry_count", DEFAULT_RETRY_COUNT))
    retry_count = max(0, min(retry_count, MAX_RETRY_COUNT))
    backoff_ms = int(config.get("retry_backoff_ms", DEFAULT_BACKOFF_MS))
    backoff_ms = max(0, min(backoff_ms, MAX_BACKOFF_MS))
    default_path = config.get("default_path") or "/"
    return {
        "allowed_hosts": allowed_hosts,
        "allowed_schemes": allowed_schemes,
        "timeout_seconds": timeout,
        "max_payload_bytes": max_payload,
        "retry_count": retry_count,
        "retry_backoff_ms": backoff_ms,
        "default_path": default_path,
    }


def build_url(host: str, path: str, allowed_schemes: list[str]) -> str:
    scheme = "https"
    if scheme not in allowed_schemes:
        raise ValueError("Webhook scheme not allowed")
    return f"{scheme}://{host}{path}"


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, connect_ip: str, port: int, timeout: int):
        super().__init__(host=host, port=port, timeout=timeout)
        self._connect_ip = connect_ip

    def connect(self) -> None:
        sock = socket.create_connection((self._connect_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def send_webhook(
    host: str,
    path: str,
    connect_ip: str,
    payload_bytes: bytes,
    headers: dict[str, str],
    timeout_seconds: int,
    retry_count: int,
    retry_backoff_ms: int,
) -> tuple[int, float]:
    """Send webhook via pinned IP. Returns (status_code, response_time_ms)."""
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            start = time.perf_counter()
            req_headers = dict(headers)
            req_headers.setdefault("Host", host)
            conn = _PinnedHTTPSConnection(host=host, connect_ip=connect_ip, port=443, timeout=timeout_seconds)
            conn.request("POST", path, body=payload_bytes, headers=req_headers)
            resp = conn.getresponse()
            status_code = resp.status
            resp.read()
            conn.close()
            elapsed_ms = (time.perf_counter() - start) * 1000
            if 300 <= status_code < 400:
                raise ValueError("Webhook redirect not allowed")
            if status_code >= 500 and attempt < retry_count:
                time.sleep(retry_backoff_ms / 1000 * (attempt + 1))
                continue
            if status_code >= 400:
                raise ValueError(f"Webhook HTTP {status_code}")
            return status_code, elapsed_ms
        except TimeoutError as e:
            last_error = e
            if attempt < retry_count:
                time.sleep(retry_backoff_ms / 1000 * (attempt + 1))
                continue
            raise ValueError("Webhook timeout") from e
        except OSError as e:
            last_error = e
            if attempt < retry_count:
                time.sleep(retry_backoff_ms / 1000 * (attempt + 1))
                continue
            raise ValueError("Webhook network error") from e
    if last_error:
        raise last_error
    raise ValueError("Webhook send failed")
