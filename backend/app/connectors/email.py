"""IN-11: Email send via SMTP. Approval-gated; no PII in logs."""
from __future__ import annotations

import hashlib
import re
import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

TIMEOUT_SEC = 30
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 2.0


def _extract_domain(addr: str) -> str:
    """Extract domain from email address. Returns 'unknown' if invalid."""
    if not addr or not isinstance(addr, str):
        return "unknown"
    addr = addr.strip()
    match = re.search(r"@([a-zA-Z0-9][-a-zA-Z0-9.]*\.[a-zA-Z]{2,})", addr)
    return match.group(1).lower() if match else "unknown"


def _sha256_hash(text: str) -> str:
    """SHA256 hash for audit (no content)."""
    return hashlib.sha256((text or "").encode()).hexdigest()[:32]


def send_email_smtp(
    host: str,
    port: int,
    username: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    content_type: str = "text/plain",
    use_tls: bool = True,
) -> tuple[str | None, int]:
    """
    Send email via SMTP. Returns (message_id, latency_ms).
    Raises ValueError on failure.
    """
    if not (host or "").strip():
        raise ValueError("SMTP host is required")
    if not (to_addr or "").strip():
        raise ValueError("Recipient email is required")
    if not (from_addr or "").strip():
        raise ValueError("From address is required")

    port = int(port) if port else (587 if use_tls else 25)
    last_error: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            start = time.perf_counter()
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject[:998] if subject else "(no subject)"
            msg["From"] = from_addr
            msg["To"] = to_addr
            part = MIMEText((body or ""), "html" if content_type == "text/html" else "plain", "utf-8")
            msg.attach(part)

            context = ssl.create_default_context() if use_tls else None
            with smtplib.SMTP(host, port, timeout=TIMEOUT_SEC) as server:
                if use_tls:
                    server.starttls(context=context)
                if username and password:
                    server.login(username.strip(), password)
                server.sendmail(from_addr, [to_addr.strip()], msg.as_string())

            msg_id = msg.get("Message-ID", "")
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return (msg_id if msg_id else None), elapsed_ms
        except smtplib.SMTPException as e:
            last_error = e
            if attempt < MAX_RETRIES and _is_retryable_smtp(e):
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ValueError(f"SMTP error: {e}") from e
        except (OSError, TimeoutError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise ValueError("SMTP connection failed") from e

    if last_error:
        raise ValueError(str(last_error)) from last_error
    return None, 0


def _is_retryable_smtp(e: smtplib.SMTPException) -> bool:
    """True for transient errors (rate limit, temp failure)."""
    msg = str(e).lower()
    return "421" in msg or "450" in msg or "451" in msg or "452" in msg or "temporarily" in msg


def extract_to_domain(to_addr: str) -> str:
    """Safe domain extraction for audit."""
    return _extract_domain(to_addr)


def subject_hash(subject: str) -> str:
    """Hash for audit."""
    return _sha256_hash(subject)


def body_hash(body: str) -> str:
    """Hash for audit."""
    return _sha256_hash(body)
