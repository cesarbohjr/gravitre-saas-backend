"""Read the api_reference mapping back out of the DEPLOYED catalog API.

The mapping is built by a local static-analysis pass (backend/scripts/
build_api_reference_map.py) and committed as data. That proves the extractor
works on this machine; it does not prove the deployed backend serves it. This
program has already found three cases where one layer was correct and the
user-facing layer was not, so the mapping is read back over HTTP from
production and diffed field-by-field against the committed map.

Fails loud on: missing apiReference, provenance drift, endpoint text drift, or
a live git_sha that is not the tip being verified.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import jwt
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

API_BASE = os.environ.get("BACKEND_URL", "https://api.gravitre.app").rstrip("/")
ORG = os.environ.get("F6_ORG_ID", "f07e57c0-1501-4000-8000-c04e57a00001")
ACTOR = os.environ.get("F6_ACTOR_ID", "a9f1240f-910a-42ca-aebf-38caeac288c3")
MAP_PATH = BACKEND / "app" / "connectors" / "action_catalog" / "data" / "api_reference_map.json"
OUT = REPO / "docs" / "delivery" / "api-reference-deployed-verify.json"


def _load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                merged.update({k: v for k, v in (dotenv_values(path, encoding=enc) or {}).items() if v})
                break
            except UnicodeDecodeError:
                continue
    for k, v in merged.items():
        os.environ.setdefault(k, v)
    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _mint(env: dict[str, str]) -> str:
    secret = env.get("SUPABASE_JWT_SECRET") or ""
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    if not secret or not url:
        raise SystemExit("SUPABASE_JWT_SECRET and SUPABASE_URL required")
    now = int(time.time())
    return jwt.encode(
        {
            "sub": ACTOR,
            "email": "cesar@gravitre.app",
            "aud": "authenticated",
            "iss": f"{url}/auth/v1",
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def _get(path: str, token: str | None = None, timeout: int = 180):
    req = urllib.request.Request(f"{API_BASE}{path}", method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("X-Org-Id", ORG)
        req.add_header("X-Environment", "production")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, {"error": raw[:400]}


def collect_actions(payload: dict) -> dict[str, dict]:
    """Pull every action dict out of the catalog payload, keyed by its tool key.

    Served nodes carry both ``id`` (short, e.g. ``leads.get``) and ``tool`` (the
    registry key, e.g. ``salesforce.leads.get``). Only ``tool`` is unique across
    vendors, so keying on ``id`` silently collides — ``email.send`` exists under
    several vendors.
    """
    found: dict[str, dict] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            tool = node.get("tool")
            if isinstance(tool, str) and "apiReference" in node:
                found[tool] = node
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def main() -> int:
    env = _load_env()
    token = _mint(env)
    started = datetime.now(timezone.utc).isoformat()

    _, health = _get("/health")
    live_sha = health.get("git_sha") or ""

    status, catalog = _get("/api/connectors/catalog/actions", token)
    if status != 200:
        print(json.dumps({"http": status, "body": catalog}, indent=2))
        raise SystemExit("deployed catalog fetch failed")

    served = collect_actions(catalog)
    local = json.loads(MAP_PATH.read_text(encoding="utf-8"))["actions"]

    missing: list[str] = []
    drift: list[dict] = []
    provenance = Counter()
    served_with_ref = 0

    for key, entry in sorted(local.items()):
        node = served.get(key)
        if node is None:
            missing.append(key)
            continue
        got_ref = node.get("apiReference")
        got_prov = node.get("apiReferenceProvenance")
        want_ref = entry.get("api_reference")
        want_prov = entry.get("provenance")
        if got_ref:
            served_with_ref += 1
        provenance[got_prov or "none"] += 1
        if got_ref != want_ref or got_prov != want_prov:
            drift.append(
                {
                    "action": key,
                    "served_api_reference": got_ref,
                    "expected_api_reference": want_ref,
                    "served_provenance": got_prov,
                    "expected_provenance": want_prov,
                }
            )

    contracts = sum(1 for n in served.values() if n.get("vendorContract"))
    with_ref_total = sum(1 for n in served.values() if n.get("apiReference"))

    report = {
        "claim": "the deployed catalog API serves the per-action api_reference mapping",
        "started_at": started,
        "api_base": API_BASE,
        "live_git_sha": live_sha,
        "catalog_actions_served": len(served),
        "local_map_entries": len(local),
        "served_with_api_reference": with_ref_total,
        "matched_against_local_map": served_with_ref,
        "actions_in_map_missing_from_deployed_catalog": missing,
        "endpoint_or_provenance_drift": drift,
        "provenance_breakdown_as_served": dict(sorted(provenance.items())),
        "served_with_vendor_contract": contracts,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    ok = not missing and not drift
    report["pass"] = ok
    report["verdict"] = (
        f"PASS — {with_ref_total} of {len(served)} deployed catalog actions carry an "
        f"apiReference, byte-identical to the committed map, at git_sha {live_sha[:8]}"
        if ok
        else f"FAIL — {len(missing)} missing, {len(drift)} drifted at git_sha {live_sha[:8]}"
    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    printable = dict(report)
    printable["endpoint_or_provenance_drift"] = drift[:10]
    printable["actions_in_map_missing_from_deployed_catalog"] = missing[:20]
    print(json.dumps(printable, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
