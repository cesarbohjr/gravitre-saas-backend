"""Bring-your-own file storage (enterprise): uploaded files go to the org's own bucket.

Scope, stated plainly: only *files* move (raw RAG uploads, chat-hosted documents).
Database rows (agent memories, RAG documents/chunks, embeddings, conversations, audit
logs) always stay in Gravitre's Supabase database.

New uploads go to the org's S3-compatible bucket only when all three hold:
  1. BYO_STORAGE_ENABLED=true (global flag, default off);
  2. the org has the ``byo_storage`` entitlement (Command / enterprise plan, the plan
     feature, or the ``byo_storage`` add-on);
  3. the org saved a target and its last connection test passed (status 'verified').
Otherwise uploads go to Supabase Storage exactly as before. With the flag on, every
upload is recorded in org_file_objects with where it went, and reads resolve from
that record (a file stays readable from where it was written, whatever the flag or
target says later; a file in a removed target cannot be read and says so).

Credentials (access key id and secret) are encrypted with the connector secrets key
(``app.connectors.crypto``, CONNECTOR_SECRETS_ENCRYPTION_KEY) and are never returned
by the API or logged. The endpoint must be HTTPS on a public address (checked on save
and before every connection, so a name cannot later point at an internal address).
Needs migration 20261020081535_storage_retention_metering.sql (and its parts).
"""
from __future__ import annotations

import ipaddress
import re
import socket
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.core.logging import get_logger

logger = get_logger(__name__)

TARGETS_TABLE = "org_storage_targets"
OBJECTS_TABLE = "org_file_objects"
SIGNED_URL_TTL_SECONDS = 3600
PROBE_PREFIX = ".gravitre-probe"

_BUCKET_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_REGION_RE = re.compile(r"^[a-z0-9-]{2,32}$")
_PREFIX_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._=-]+$")
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}


class ByoStorageError(ValueError):
    """Invalid target configuration or an unusable target; the message is safe to show."""


class ByoStorageUnavailableError(RuntimeError):
    """A file was written to the org's own bucket, which is no longer configured."""


# --------------------------------------------------------------------------- config


def _encryption_key(settings: Any) -> str:
    key = (getattr(settings, "connector_secrets_encryption_key", "") or "").strip()
    if not key:
        raise ByoStorageError("Storage credentials cannot be saved: encryption is not configured on the server.")
    return key


def validate_endpoint(endpoint_url: str | None, *, resolve: bool = True) -> str | None:
    """Return a normalized https endpoint (None = the provider default) or raise."""
    raw = (endpoint_url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ByoStorageError("The endpoint must be an https:// address without a user name or password.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ByoStorageError("The endpoint must be just the server address, without a path.")
    if host in _BLOCKED_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise ByoStorageError("The endpoint must be a public address.")
    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    try:
        addresses.add(ipaddress.ip_address(host))
    except ValueError:
        if resolve:
            try:
                infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise ByoStorageError("The endpoint address could not be found.") from exc
            for info in infos:
                try:
                    addresses.add(ipaddress.ip_address(str(info[4][0])))
                except (ValueError, IndexError):
                    continue
            if not addresses:
                raise ByoStorageError("The endpoint address could not be found.")
    for addr in addresses:
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            raise ByoStorageError("The endpoint must be a public address.")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{host}{port}"


def normalize_prefix(prefix: str | None) -> str:
    raw = (prefix or "").strip().strip("/")
    if not raw:
        return ""
    segments = [s for s in raw.split("/") if s]
    if len(raw) > 200 or any(s in {".", ".."} or not _PREFIX_SEGMENT_RE.match(s) for s in segments):
        raise ByoStorageError("The folder prefix may use letters, numbers, '.', '_', '-', '=' and '/'.")
    return "/".join(segments)


def validate_target_input(body: dict[str, Any], *, resolve: bool = True) -> dict[str, Any]:
    bucket = str(body.get("bucket") or "").strip()
    region = str(body.get("region") or "").strip().lower()
    if not _BUCKET_RE.match(bucket) or ".." in bucket:
        raise ByoStorageError("Enter a valid bucket name (3-63 lowercase letters, numbers, '.' or '-').")
    if not _REGION_RE.match(region):
        raise ByoStorageError("Enter a valid region, for example us-east-1.")
    return {
        "endpoint_url": validate_endpoint(body.get("endpointUrl"), resolve=resolve),
        "region": region,
        "bucket": bucket,
        "path_prefix": normalize_prefix(body.get("pathPrefix")),
    }


# --------------------------------------------------------------------------- targets


def load_target(client: Any, org_id: str) -> dict[str, Any] | None:
    res = client.table(TARGETS_TABLE).select("*").eq("org_id", org_id).limit(1).execute()
    rows = res.data or []
    return dict(rows[0]) if rows else None


def public_target_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the API may show: never the credentials, only the last 4 characters of the key id."""
    if not row:
        return None
    return {
        "provider": row.get("provider") or "s3",
        "endpointUrl": row.get("endpoint_url"),
        "region": row.get("region"),
        "bucket": row.get("bucket"),
        "pathPrefix": row.get("path_prefix") or "",
        "accessKeyHint": row.get("access_key_hint"),
        "status": row.get("status") or "untested",
        "lastTestedAt": row.get("last_tested_at"),
        "lastTestError": row.get("last_test_error"),
        "updatedAt": row.get("updated_at"),
    }


def save_target(
    client: Any, settings: Any, org_id: str, user_id: str | None, body: dict[str, Any]
) -> dict[str, Any]:
    """Create or replace the org's target. Credentials are required on create; on update
    leaving both empty keeps the stored ones. Any change resets the status to 'untested'."""
    clean = validate_target_input(body)
    key = _encryption_key(settings)
    access_key_id = str(body.get("accessKeyId") or "").strip()
    secret = str(body.get("secretAccessKey") or "").strip()
    existing = load_target(client, org_id)
    now = datetime.now(UTC).isoformat()
    row: dict[str, Any] = {
        "org_id": org_id,
        "provider": "s3",
        **clean,
        "status": "untested",
        "last_test_error": None,
        "updated_by": user_id,
        "updated_at": now,
    }
    if access_key_id or secret:
        if not (access_key_id and secret):
            raise ByoStorageError("Enter both the access key id and the secret access key.")
        row["access_key_id_enc"] = encrypt_secret(access_key_id, key)
        row["secret_access_key_enc"] = encrypt_secret(secret, key)
        row["access_key_hint"] = access_key_id[-4:]
    elif not existing:
        raise ByoStorageError("Enter the access key id and the secret access key.")
    if not existing:
        row["created_by"] = user_id
    client.table(TARGETS_TABLE).upsert(row, on_conflict="org_id").execute()
    return public_target_view(load_target(client, org_id)) or {}


def delete_target(client: Any, org_id: str) -> bool:
    res = client.table(TARGETS_TABLE).delete().eq("org_id", org_id).execute()
    return bool(res.data)


def _credentials(settings: Any, row: dict[str, Any]) -> tuple[str, str]:
    key = _encryption_key(settings)
    return (
        decrypt_secret(str(row["access_key_id_enc"]), key),
        decrypt_secret(str(row["secret_access_key_enc"]), key),
    )


def s3_client(settings: Any, row: dict[str, Any]) -> Any:
    """boto3 S3 client for the target. Re-checks the endpoint address every time."""
    import boto3
    from botocore.config import Config

    endpoint = validate_endpoint(row.get("endpoint_url"))
    access_key_id, secret = _credentials(settings, row)
    config = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path" if endpoint else "auto"},
        retries={"max_attempts": 2, "mode": "standard"},
        connect_timeout=5,
        read_timeout=20,
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=str(row.get("region") or "us-east-1"),
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret,
        config=config,
    )


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        code = (response.get("Error") or {}).get("Code")
        if code:
            return str(code)[:80]
    return type(exc).__name__


def object_key(row: dict[str, Any], logical_bucket: str, logical_path: str) -> str:
    parts = [p for p in (row.get("path_prefix") or "", logical_bucket, logical_path) if p]
    return "/".join(s.strip("/") for s in parts)


def probe_target(client: Any, settings: Any, org_id: str) -> dict[str, Any]:
    """Put, read back (head) and delete a small probe object; store the outcome."""
    row = load_target(client, org_id)
    if not row:
        raise ByoStorageError("No storage target is configured.")
    steps: dict[str, bool] = {"put": False, "head": False, "delete": False}
    error: str | None = None
    try:
        s3 = s3_client(settings, row)
        key = object_key(row, PROBE_PREFIX, f"{uuid.uuid4().hex}.txt")
        s3.put_object(Bucket=row["bucket"], Key=key, Body=b"gravitre storage probe", ContentType="text/plain")
        steps["put"] = True
        s3.head_object(Bucket=row["bucket"], Key=key)
        steps["head"] = True
        s3.delete_object(Bucket=row["bucket"], Key=key)
        steps["delete"] = True
    except ByoStorageError as exc:
        error = str(exc)
    except Exception as exc:  # noqa: BLE001 - provider error codes only, never request details
        error = f"The storage service answered {_error_code(exc)}."
    ok = all(steps.values())
    now = datetime.now(UTC).isoformat()
    client.table(TARGETS_TABLE).update(
        {"status": "verified" if ok else "failed", "last_tested_at": now, "last_test_error": error}
    ).eq("org_id", org_id).execute()
    logger.info("byo_storage_test org_id=%s ok=%s steps=%s", org_id, ok, steps)
    return {"ok": ok, "steps": steps, "error": error, "testedAt": now}


# --------------------------------------------------------------------------- routing


def org_entitled(settings: Any, org_id: str) -> bool:
    try:
        from app.middleware.entitlements import resolve_entitlements

        features = resolve_entitlements(settings, org_id).get("features") or {}
    except Exception as exc:  # noqa: BLE001 - unknown entitlement: not entitled
        logger.warning("byo_storage_entitlement_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return False
    return bool(features.get("byo_storage"))


def active_target(client: Any, settings: Any, org_id: str | None) -> dict[str, Any] | None:
    """The org's verified target when the flag and the entitlement allow it, else None."""
    if not org_id or getattr(settings, "byo_storage_enabled", False) is not True:
        return None
    if not org_entitled(settings, org_id):
        return None
    try:
        row = load_target(client, org_id)
    except Exception as exc:  # noqa: BLE001 - table missing or read error: keep Supabase
        logger.warning("byo_storage_target_read_failed org_id=%s error=%s", org_id, type(exc).__name__)
        return None
    if not row or row.get("status") != "verified":
        return None
    return row


def _record_object(client: Any, record: dict[str, Any]) -> None:
    try:
        client.table(OBJECTS_TABLE).upsert(record, on_conflict="org_id,logical_bucket,logical_path").execute()
    except Exception as exc:  # noqa: BLE001 - the file is stored; a missing record reads as Supabase
        logger.warning(
            "org_file_object_record_failed org_id=%s location=%s error=%s",
            record.get("org_id"), record.get("location"), type(exc).__name__,
        )


def put_org_file(
    client: Any,
    settings: Any,
    *,
    org_id: str | None,
    logical_bucket: str,
    path: str,
    data: bytes,
    content_type: str | None,
    purpose: str,
    upsert: bool = True,
) -> dict[str, Any]:
    """Store one uploaded file and return its metadata. Raises on upload failure.

    With BYO_STORAGE_ENABLED off this is exactly the previous Supabase upload and
    returns the previous keys only.
    """
    meta: dict[str, Any] = {"storage_bucket": logical_bucket, "storage_path": path, "storage_bytes": len(data)}
    flag_on = getattr(settings, "byo_storage_enabled", False) is True
    target = active_target(client, settings, org_id) if flag_on else None
    if target is not None:
        key = object_key(target, logical_bucket, path)
        extra: dict[str, Any] = {"ContentType": content_type} if content_type else {}
        s3_client(settings, target).put_object(Bucket=target["bucket"], Key=key, Body=data, **extra)
        location, bucket = "byo", str(target["bucket"])
    else:
        file_options: dict[str, Any] = {"upsert": "true" if upsert else "false"}
        if content_type:
            file_options["content-type"] = content_type
        client.storage.from_(logical_bucket).upload(path, data, file_options=file_options)
        location, bucket, key = "supabase", logical_bucket, path
    if not flag_on or not org_id:
        return meta
    _record_object(
        client,
        {
            "org_id": org_id,
            "location": location,
            "bucket": bucket,
            "object_key": key,
            "logical_bucket": logical_bucket,
            "logical_path": path,
            "byte_size": len(data),
            "content_type": content_type,
            "purpose": purpose,
        },
    )
    meta["storage_location"] = location
    return meta


def _supabase_signed_url(client: Any, bucket: str, path: str, ttl: int) -> str | None:
    signed = client.storage.from_(bucket).create_signed_url(path, ttl)
    if isinstance(signed, dict):
        return signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url")
    if isinstance(signed, str):
        return signed
    return None


def resolve_download_url(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    logical_bucket: str,
    path: str,
    ttl: int = SIGNED_URL_TTL_SECONDS,
) -> dict[str, Any]:
    """A time-limited URL for a stored file, from wherever it was written.

    No org_file_objects record (written before this feature, or with the flag off)
    means Supabase Storage. Raises ByoStorageUnavailableError for a file in the org's
    own bucket when that target has since been removed. Only the org's own files:
    the path must start with the org id (every upload path does).
    """
    if path.split("/", 1)[0] != org_id or ".." in path.split("/"):
        raise ByoStorageError("File not found.")
    record: dict[str, Any] | None = None
    try:
        res = (
            client.table(OBJECTS_TABLE)
            .select("location, bucket, object_key")
            .eq("org_id", org_id)
            .eq("logical_bucket", logical_bucket)
            .eq("logical_path", path)
            .limit(1)
            .execute()
        )
        record = dict(res.data[0]) if res.data else None
    except Exception as exc:  # noqa: BLE001 - table not there yet: everything is in Supabase
        logger.info("org_file_object_lookup_skipped error=%s", type(exc).__name__)
    if record and record.get("location") == "byo":
        target = load_target(client, org_id)
        if not target:
            raise ByoStorageUnavailableError(
                "This file is stored in your organization's own storage, which is no longer connected."
            )
        url = s3_client(settings, target).generate_presigned_url(
            "get_object",
            Params={"Bucket": record.get("bucket") or target["bucket"], "Key": record["object_key"]},
            ExpiresIn=int(ttl),
        )
        return {"location": "byo", "url": url, "expiresIn": int(ttl)}
    bucket = str((record or {}).get("bucket") or logical_bucket)
    key = str((record or {}).get("object_key") or path)
    return {"location": "supabase", "url": _supabase_signed_url(client, bucket, key, int(ttl)), "expiresIn": int(ttl)}
