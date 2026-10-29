"""Fail-closed pre-production adapter selection decision.

A passing Chromium fixture is evidence, never authorization to replace the
native execution adapter. Missing comparative measurements remain BLOCKED.
"""
from __future__ import annotations

REQUIRED = (
    "tenant_authorization",
    "gateway_enforcement",
    "crash_recovery",
    "representative_reliability",
    "representative_cost",
    "security_review",
)

def evaluate(microbenchmark: dict, comparative: dict | None = None) -> dict:
    comparative = comparative or {}
    complete = microbenchmark.get("microbenchmark_passed") is True
    gates = {}
    for name in REQUIRED:
        item = comparative.get(name)
        valid = isinstance(item, dict) and item.get("result") == "PASS" and item.get("both_adapters") is True and isinstance(item.get("evidence_sha256"), str) and len(item["evidence_sha256"]) == 64 and all(c in "0123456789abcdef" for c in item["evidence_sha256"])
        gates[name] = "PASS" if valid else "BLOCKED"
    selected = all(v == "PASS" for v in gates.values()) and complete
    return {
        "existing_adapter": "browser_use",
        "candidate": "playwright",
        "microbenchmark": "PASS" if complete else "FAIL",
        "comparative_gates": gates,
        "selection": "ELIGIBLE_FOR_HUMAN_REVIEW" if selected else "RETAIN_BROWSER_USE_COMPARISON_INCOMPLETE",
        "production_certified": False,
    }
