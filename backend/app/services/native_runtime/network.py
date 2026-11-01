"""Exact HTTPS egress policy; pin a validated public address for every CONNECT."""
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlsplit


def public_addresses(host: str) -> list[str]:
    if host.lower() in {'localhost','metadata.google.internal'} or host.endswith(('.localhost','.local','.internal')):raise ValueError('Private destination rejected')
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise ValueError('IP literals are not browser destinations')
    rows=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(r[4][0] for r in rows))
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):raise ValueError('Destination resolves outside the public Internet')
    return addresses


def approved_url(url: str, allowed_hosts: list[str]) -> str:
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in allowed_hosts or u.port not in (None,443) or u.username or u.password or '\\' in url or any(ord(c)<33 for c in url):
        raise ValueError('Browser destination outside approved HTTPS scope')
    return u.hostname
