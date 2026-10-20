#!/usr/bin/env python3
"""Fail-closed verifier for a separately executed, isolated intelligence E2E scenario.

This script never creates production data. The scenario executor must provide a
JSON evidence bundle collected from authenticated readbacks and audit records.
A staging/isolated-tenant runner must perform the scenario itself.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = (
    "trace_id", "org_id", "conversation_id", "signal_id", "context_id",
    "sentiment_id", "recommendation_id", "approval_id", "actor_id",
    "action_id", "provider_write_id", "readback_id", "outcome_id",
    "learning_delivery_id",
)

def verify(evidence: dict, *, expected_org: str) -> list[str]:
    errors = []
    for key in REQUIRED:
        if not isinstance(evidence.get(key), str) or not evidence[key].strip():
            errors.append(f"missing_{key}")
    if evidence.get("org_id") != expected_org:
        errors.append("wrong_org")
    if evidence.get("synthetic_only") is not True:
        errors.append("not_synthetic")
    for key in ("approval_bound_to_actor", "approval_bound_to_conversation",
                "approved_before_execution", "provider_readback_verified",
                "business_metric_verified", "learning_attributed_to_outcome",
                "cross_tenant_denied", "duplicate_approval_no_second_write",
                "changed_draft_requires_reapproval", "failed_work_not_measured"):
        if evidence.get(key) is not True:
            errors.append(f"unverified_{key}")
    if evidence.get("provider_write_count") != 1:
        errors.append("provider_write_count_not_one")
    if evidence.get("outcome_id") and evidence.get("learning_parent_outcome_id") != evidence.get("outcome_id"):
        errors.append("learning_outcome_correlation_missing")
    if evidence.get("approval_action_id") != evidence.get("action_id"):
        errors.append("approval_action_binding_missing")
    if evidence.get("queued_counted_as_measured") is not False:
        errors.append("queued_counting_unverified")
    if evidence.get("predicted_as_measured") is not False:
        errors.append("prediction_counting_unverified")
    if evidence.get("evidence_source") != "authenticated_runtime_readback":
        errors.append("not_runtime_evidence")
    return errors

def delivery(base: str, token: str, org_id: str) -> tuple[dict, list[str]]:
    url = base.rstrip("/") + "/api/admin/intelligence/outcomes/delivery"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org_id,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status != 200:
                return {}, [f"delivery_http_{response.status}"]
            payload = json.loads(response.read(1048576).decode())
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return {}, [f"delivery_unavailable_{type(exc).__name__}"]
    if not isinstance(payload, dict):
        return {}, ["delivery_invalid_payload"]
    issues = []
    if payload.get("status") not in ("idle", "queued"):
        issues.append("delivery_not_active")
    if payload.get("blockers"):
        issues.append("delivery_has_blockers")
    return payload, issues

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--org-id", required=True)
    p.add_argument("--api-base", default="https://api.gravitre.app")
    p.add_argument("--out", type=Path, default=Path("intelligence-e2e-verdict.json"))
    args = p.parse_args()
    token = os.environ.get("GRAVITRE_E2E_BEARER_TOKEN", "")
    errors = []
    if not token:
        errors.append("missing_authentication")
    try:
        bundle = json.loads(args.evidence.read_text(encoding="utf-8"))
        if not isinstance(bundle, dict):
            raise ValueError("not object")
    except (OSError, ValueError) as exc:
        bundle = {}
        errors.append(f"evidence_unavailable_{type(exc).__name__}")
    errors += verify(bundle, expected_org=args.org_id)
    response = {}
    if token:
        response, issues = delivery(args.api_base, token, args.org_id)
        errors += issues
    result = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "verdict": "PASS" if not errors else "FAIL",
        "errors": sorted(set(errors)),
        "trace_id": bundle.get("trace_id"),
        "delivery_status": response.get("status", "unknown"),
        "note": "Evidence must originate from independently authenticated runtime readbacks; declarations alone are not cryptographic proof.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1

if __name__ == "__main__":
    sys.exit(main())
