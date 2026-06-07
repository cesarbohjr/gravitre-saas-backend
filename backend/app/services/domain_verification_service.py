"""Custom domain CNAME / TXT verification for white-label branding (STA-84)."""
from __future__ import annotations

import secrets
import socket
from typing import Any

try:
    import dns.resolver  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - optional dependency
    dns = None  # type: ignore[assignment]


def generate_verification_token() -> str:
    return secrets.token_urlsafe(24)


def verification_txt_host(domain: str) -> str:
    cleaned = domain.strip().lower().rstrip(".")
    return f"_gravitre.{cleaned}"


def build_verification_instructions(
    *,
    domain: str,
    token: str,
    cname_target: str,
) -> dict[str, Any]:
    return {
        "domain": domain.strip().lower(),
        "verificationToken": token,
        "cnameTarget": cname_target.rstrip("."),
        "cnameRecord": {
            "type": "CNAME",
            "host": domain.strip().lower(),
            "value": cname_target.rstrip("."),
        },
        "txtRecord": {
            "type": "TXT",
            "host": verification_txt_host(domain),
            "value": f"gravitre-verify={token}",
        },
    }


def _resolve_cname(domain: str) -> list[str]:
    if dns is not None:
        try:
            answers = dns.resolver.resolve(domain.strip().lower().rstrip("."), "CNAME")
            return [str(r.target).rstrip(".").lower() for r in answers]
        except Exception:  # noqa: BLE001
            return []
    try:
        canonical = socket.getaddrinfo(domain, None)
        _ = canonical
    except OSError:
        pass
    return []


def _resolve_txt(host: str) -> list[str]:
    if dns is None:
        return []
    try:
        answers = dns.resolver.resolve(host.strip().lower().rstrip("."), "TXT")
        values: list[str] = []
        for answer in answers:
            if hasattr(answer, "strings"):
                for chunk in answer.strings:
                    values.append(chunk.decode("utf-8", errors="ignore"))
            else:
                values.append(str(answer).strip('"'))
        return values
    except Exception:  # noqa: BLE001
        return []


def verify_custom_domain(
    *,
    domain: str,
    token: str,
    cname_target: str,
) -> dict[str, Any]:
    """Verify domain ownership via CNAME to platform target or TXT token."""
    cleaned_domain = domain.strip().lower().rstrip(".")
    expected_target = cname_target.strip().lower().rstrip(".")
    expected_txt = f"gravitre-verify={token.strip()}"

    cname_matches = [target for target in _resolve_cname(cleaned_domain) if target == expected_target]
    txt_values = _resolve_txt(verification_txt_host(cleaned_domain))
    txt_matches = [value for value in txt_values if expected_txt in value]

    verified = bool(cname_matches or txt_matches)
    method = "cname" if cname_matches else ("txt" if txt_matches else None)
    return {
        "verified": verified,
        "method": method,
        "checks": {
            "cname": {"expected": expected_target, "found": cname_matches},
            "txt": {"expected": expected_txt, "found": txt_matches},
        },
    }
