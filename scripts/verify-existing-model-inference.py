"""Bounded live inference evidence using an existing, explicitly supplied session.

Does not mint tokens, choose a customer, change consent, create or deploy models.
Inputs stay in the operator's private case file; reports contain metadata only.
Inference can incur approved provider costs and writes normal prediction logs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(base, path, token=None, org=None, body=None):
    headers = {"Accept": "application/json", "X-Environment": "production"}
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-Org-Id"] = org
    data = None if body is None else json.dumps(body, allow_nan=False).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers)
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=60) as response:
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Response exceeds evidence limit")
        return json.loads(raw)


def validated_cases(path):
    if path.stat().st_size > 65536:
        raise ValueError("Private case file exceeds 64 KiB")
    cases = json.loads(path.read_text())
    if not isinstance(cases, list) or not 1 <= len(cases) <= 26:
        raise ValueError("Supply 1–26 explicit existing model cases")
    identities = set()
    for case in cases:
        UUID(case["model_id"])
        if (type(case.get("version")) is not int or case["version"] < 1
                or not isinstance(case.get("inputs"), list) or not 1 <= len(case["inputs"]) <= 4
                or any(not isinstance(row, dict) or not row for row in case["inputs"])):
            raise ValueError("Each case needs a positive version and 1–4 nonempty input objects")
        identity = (case["model_id"], case["version"])
        if identity in identities:
            raise ValueError("Duplicate inference case")
        identities.add(identity)
    return cases


def verify_result(result, case):
    if (not isinstance(result, dict) or result.get("model_id") != case["model_id"]
            or type(result.get("version")) is not int or result["version"] != case["version"]
            or not isinstance(result.get("predictions"), list)
            or len(result["predictions"]) != len(case["inputs"])):
        raise ValueError("Exact model/version and one prediction per input required")
    def meaningful(value):
        if isinstance(value, dict):
            return bool(value) and all(meaningful(item) for item in value.values())
        if isinstance(value, list):
            return bool(value) and all(meaningful(item) for item in value)
        if type(value) in {int, float}:
            return math.isfinite(value)
        return isinstance(value, bool) or isinstance(value, str) and bool(value.strip())
    if not all(meaningful(value) for value in result["predictions"]):
        raise ValueError("Empty or nonfinite prediction")
    latency = result.get("latency_ms")
    if type(latency) not in {int, float} or not math.isfinite(latency) or latency < 0:
        raise ValueError("Valid measured inference latency required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="https://api.gravitre.app")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--org")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    base = args.base.rstrip("/")
    url = urllib.parse.urlsplit(base)
    # Never forward an operator session to a URL from a case file or redirect.
    if (url.scheme != "https" or url.hostname not in {"api.gravitre.app", "gravitre-saas-backend-production.up.railway.app"}
            or url.port not in {None,443} or url.username or url.password or url.path or url.query or url.fragment
            or not re.fullmatch(r"[a-f0-9]{40}", args.expected_sha)):
        parser.error("Known production HTTPS host and exact expected commit SHA required")
    cases = validated_cases(args.cases) if args.cases else []
    token = os.environ.get("ML_VERIFICATION_SESSION", "")
    if cases and (not args.org or not token):
        parser.error("Explicit organization and ML_VERIFICATION_SESSION required for inference")
    if args.org:
        UUID(args.org)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "target": base,
              "expected_sha": args.expected_sha, "health": "not_run", "inference": "not_run",
              "provider_execution": "not_verified", "cases": []}
    code = 2
    try:
        health = request(base, "/health")
        if health.get("git_sha") != args.expected_sha or health.get("status") != "ok":
            raise ValueError("Production health/commit alignment failed")
        report["health"] = "pass"
        report["observed_sha"] = health["git_sha"]
        for case in cases:
            result = request(base, f'/api/ml/models/{case["model_id"]}/predict', token, args.org,
                {"version": case["version"], "inputs": case["inputs"], "return_probabilities": True})
            verify_result(result, case)
            report["cases"].append({"model_id": case["model_id"], "version": case["version"],
                "status": "pass", "predictions": len(result["predictions"]), "latency_ms": result["latency_ms"]})
        if cases:
            report["inference"] = "pass"
            code = 0
        else:
            report["blocker"] = "No authorized organization session and approved inference cases supplied"
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as exc:
        # Server error bodies can contain customer content; never include them.
        report["error_type"] = type(exc).__name__
        report["inference"] = "fail" if cases else "not_run"
        code = 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    os.chmod(args.report, 0o600)
    print(json.dumps({"health": report["health"], "inference": report["inference"], "report": str(args.report)}))
    return code


if __name__ == "__main__":
    sys.exit(main())
