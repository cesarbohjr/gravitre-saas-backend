"""Fail-closed interpretation of canonical Play source-of-record outcome evidence."""
from __future__ import annotations
from typing import Any

VERIFIED_STATES = frozenset({"VERIFIED SUCCESS", "VERIFIED FAILURE"})

def verified_business_evidence(state: str, chain: Any) -> bool:
    if state not in VERIFIED_STATES or not isinstance(chain, dict):
        return False
    proof = chain.get("verification")
    if not isinstance(proof, dict):
        return False
    if proof.get("verified") is not True or proof.get("state") != state:
        return False
    if not str(proof.get("method") or "").strip():
        return False
    if state == "VERIFIED FAILURE":
        return True
    # A positive business claim requires a source-of-record and a measured
    # before/after metric. A successful Play run alone never qualifies.
    sources = chain.get("sourceRecords")
    metric = chain.get("metric")
    if not isinstance(sources, list) or not any(
        isinstance(row, dict)
        and str(row.get("system") or "").strip()
        and str(row.get("record_id") or "").strip()
        for row in sources
    ):
        return False
    if not isinstance(metric, dict) or not str(metric.get("key") or "").strip():
        return False
    if metric.get("baseline") is None or metric.get("result") is None:
        return False
    return True
