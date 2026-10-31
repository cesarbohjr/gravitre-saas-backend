"""Research-only candidate boundaries. No SDK import, transport or activation."""
from dataclasses import dataclass
import hashlib
import hmac
import json


@dataclass(frozen=True)
class Scope:
    org_id: str
    user_id: str
    agent_id: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() or v != v.strip() for v in (self.org_id, self.user_id, self.agent_id)):
            raise ValueError("Complete authenticated scope is required")


def _ref(scope, kind, key):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("A dedicated research namespace key is required")
    parts = [scope.org_id, kind, scope.user_id if kind == "subject" else scope.agent_id]
    return hmac.new(key, json.dumps(parts, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()


def mem0_search_contract(scope: Scope, query: str, *, namespace_key: bytes):
    """Pinned current OSS search shape: identity belongs in filters, not kwargs.

    This request is data only. It grants no consent or vendor access. An actual
    runner must authorize before calling and recheck consent on returned hits.
    """
    if not isinstance(query, str) or not 0 < len(query.strip()) <= 2000:
        raise ValueError("Bounded synthetic query required")
    return {"query": query, "top_k": 8, "filters": {
        "user_id": _ref(scope, "subject", namespace_key),
        "agent_id": _ref(scope, "agent", namespace_key),
    }}


def canonical_mem0_hit_ids(response, *, trusted_bindings: dict[str, str]):
    """Vendor IDs resolve through host-owned bindings; vendor text is ignored.

    Returned IDs are only candidates. The existing authoritative tenant/agent/
    subject, consent, retention, liveness and quarantine gates must still run.
    """
    if not isinstance(response, dict) or not isinstance(response.get("results"), list) or len(response["results"]) > 50:
        raise ValueError("Invalid bounded candidate response")
    result = []
    for row in response["results"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError("Invalid candidate identity")
        canonical = trusted_bindings.get(row["id"])
        if canonical is not None and (not isinstance(canonical, str) or not canonical.strip() or len(canonical) > 200):
            raise ValueError("Invalid host-owned canonical binding")
        if canonical and canonical not in result:
            result.append(canonical)
    return result


def letta_snapshot_requirements():
    """Host contract, NOT a claimed Letta API endpoint or SDK implementation.

    Current Letta Code is a MemFS/agent harness. Any future comparison must
    provide a read-only scoped snapshot, not import its autonomous runtime.
    """
    return {"schema": 1, "transport": None, "mode": "read_only_scoped_snapshot",
            "require_authoritative_rehydration": True, "allow_self_edit": False,
            "allow_skill_or_prompt_mutation": False, "allow_cross_agent_search": False,
            "runtime_status": "NOT_RUN"}
