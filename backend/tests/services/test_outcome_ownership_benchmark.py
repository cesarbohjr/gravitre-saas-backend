"""Held-out Outcome Ownership contract benchmark.

These cases score invariants, not exact model prose, so production prompts cannot
memorize benchmark answers.
"""
from app.services.objective_capability_composer import CapabilityResource, compose_capability_resources
from app.services.outcome_recovery_policy import decide_recovery


CASES = [
    ("crm_create_timeout", "write", "timeout", True, "reconcile"),
    ("refund_timeout", "write", "connector_timeout", True, "reconcile"),
    ("workflow_timeout", "workflow", "timeout", True, "reconcile"),
    ("agent_timeout", "agent_delegation", "timeout", True, "reconcile"),
    ("read_timeout", "read", "timeout", False, "retry"),
    ("rate_limit_read", "read", "rate_limited", False, "retry"),
    ("auth_expired", "write", "auth_expired", False, "blocked"),
    ("missing_scope", "write", "missing_scope", False, "blocked"),
    ("missing_parameter", "write", "missing_parameter", False, "repair_parameters"),
    ("unknown_with_alternate", "read", "provider_error", False, "replan"),
]


def test_recovery_contract_matrix() -> None:
    for name, kind, code, uncertain, expected in CASES:
        decision = decide_recovery(
            kind=kind,
            error_code=code,
            outcome_uncertain=uncertain,
            retries_used=0,
            retry_budget=2,
            alternate_capability_available=name == "unknown_with_alternate",
        )
        assert decision.action == expected, name


def test_compound_objective_composes_heterogeneous_resources() -> None:
    resources = [
        CapabilityResource("hubspot", "connector", frozenset({"crm.read", "crm.write"}), writable=True, verified=True),
        CapabilityResource("sales-agent", "agent", frozenset({"prioritize"}), verified=True),
        CapabilityResource("followup-play", "play", frozenset({"followup"}), writable=True, verified=True),
        CapabilityResource("org-kb", "knowledge", frozenset({"company.context"}), verified=True),
        CapabilityResource("accounts", "dataset", frozenset({"account.data"}), verified=True),
        CapabilityResource("web", "internet", frozenset({"account.research"}), verified=True),
    ]
    result = compose_capability_resources(
        required_capabilities={
            "crm.read", "crm.write", "prioritize", "followup",
            "company.context", "account.data", "account.research",
        },
        resources=resources,
    )
    assert result["complete"] is True
    assert {r["kind"] for r in result["selected"]} == {
        "connector", "agent", "play", "knowledge", "dataset", "internet"
    }


def test_missing_resource_keeps_objective_incomplete() -> None:
    result = compose_capability_resources(
        required_capabilities={"crm.write", "account.research"},
        resources=[
            CapabilityResource("hubspot", "connector", frozenset({"crm.write"}), writable=True, verified=True)
        ],
    )
    assert result["complete"] is False
    assert result["missing_capabilities"] == ["account.research"]
