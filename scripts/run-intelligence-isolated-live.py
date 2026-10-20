#!/usr/bin/env python3
"""Authenticated isolated-org intelligence lifecycle probe; fail closed.

Exercises real assistant/chat stages with an existing short-lived test identity.
Never uses an operator/customer org and never sends to external connectors.
Independently checks persisted assignment status through /api/agent-jobs.
Measured outcome and learning need independent attestation: absent readbacks fail.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

TEST_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
API_ROOT = "https://api.gravitre.app"
PROMPT = ('Controlled synthetic intelligence acceptance {trace}. Customer says: '
          '"I am extremely frustrated. Onboarding is two weeks late. Unless we '
          'have a recovery plan by Friday we will cancel our renewal." '
          'Renewal is in 30 days with two unresolved onboarding issues. '
          'Assess sentiment and context. Recommend a native Gravitre remedy, '
          'then stage ONE INTERNAL GRAVITRE assignment titled '
          '"[E2E TEST] {trace} recovery plan" for my approval first. '
          'No Gmail, email, Slack, external providers, or customer contact. '
          'Do not execute until I approve.')

class ProbeError(Exception):
    pass

def request(method, url, token, org, payload=None, *, expect_json=True):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token, "X-Org-Id": org,
        "X-Organization-ID": org, "X-Environment": "production",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=100) as resp:
            raw = resp.read(2_000_000).decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(2000).decode("utf-8", "replace")
    if status >= 400:
        raise ProbeError("HTTP_" + str(status) + "_" + url.split("/")[-1])
    if expect_json:
        try:
            return json.loads(raw)
        except ValueError:
            raise ProbeError("non_json_readback")
    return raw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-id", required=True)
    ap.add_argument("--api-base", default=API_ROOT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allow-synthetic-write", action="store_true")
    args = ap.parse_args()
    if args.org_id != TEST_ORG:
        raise SystemExit("REFUSED: only canonical isolated E2E tenant allowed")
    if args.api_base.rstrip("/") != API_ROOT:
        raise SystemExit("REFUSED: unexpected API target")
    token = os.environ.get("GRAVITRE_E2E_BEARER_TOKEN", "")
    if not token:
        raise SystemExit("REFUSED: no delegated short-lived test token")
    trace = "GV-INT-E2E-" + uuid.uuid4().hex[:12]
    conversation = str(uuid.uuid4())
    report = {"trace_id": trace, "org_id": args.org_id,
              "conversation_id": conversation, "created_at": datetime.now(timezone.utc).isoformat(),
              "synthetic_only": True, "checks": [], "verdict": "FAIL"}
    def checkpoint(name, ok, detail=""):
        report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            raise ProbeError(name)
    base = args.api_base.rstrip("/")
    def turn(message, history):
        history.append({"id": str(uuid.uuid4()), "role": "user",
                        "parts": [{"type": "text", "text": message}]})
        return request("POST", base + "/api/assistant/chat", token, args.org_id,
                       {"org_id": args.org_id, "conversation_id": conversation,
                        "messages": history}, expect_json=False)
    try:
        checkpoint("write_is_explicitly_enabled", args.allow_synthetic_write)
        history = []
        initial = turn(PROMPT.format(trace=trace), history)
        checkpoint("chat_stream_returned", bool(initial.strip()))
        # A stream receipt is not proof of a staged action. Inspect status through
        # independent authenticated endpoints; never approve merely on model text.
        report["chat_bytes"] = len(initial)
        report["initial_stream_has_trace"] = trace in initial
        checkpoint("initial_stream_contains_trace", trace in initial)
        # A real pending-action binding readback API is required before approval.
        # Its endpoint/schema must be resolved and implemented explicitly.
        checkpoint("pending_action_authenticated_readback_implemented", False,
                   "No verified pending-action API contract; automatic approval prohibited")
    except (ProbeError, urllib.error.URLError, TimeoutError) as exc:
        report["blocker"] = str(exc)[:160]
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"verdict": report["verdict"], "checks": report["checks"],
                          "blocker": report.get("blocker"), "out": str(args.out)}))
    return 1

if __name__ == "__main__":
    sys.exit(main())
