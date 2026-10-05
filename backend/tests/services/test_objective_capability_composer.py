from app.services.objective_capability_composer import CapabilityResource, compose_capability_resources


def test_composes_across_connector_agent_knowledge_and_internet() -> None:
    resources = [
        CapabilityResource("crm", "connector", frozenset({"crm.read", "crm.write"}), writable=True, verified=True),
        CapabilityResource("analyst", "agent", frozenset({"analyze"}), verified=True),
        CapabilityResource("kb", "knowledge", frozenset({"company.context"}), verified=True),
        CapabilityResource("web", "internet", frozenset({"market.research"}), verified=True),
    ]
    result = compose_capability_resources(
        required_capabilities={"crm.write", "analyze", "company.context", "market.research"},
        resources=resources,
    )
    assert result["complete"] is True
    assert {x["kind"] for x in result["selected"]} == {"connector", "agent", "knowledge", "internet"}
    assert result["verification_ready"] is True


def test_missing_capability_is_explicit_not_hallucinated() -> None:
    result = compose_capability_resources(
        required_capabilities={"crm.write", "billing.refund"},
        resources=[CapabilityResource("crm", "connector", frozenset({"crm.write"}), writable=True)],
    )
    assert result["complete"] is False
    assert result["missing_capabilities"] == ["billing.refund"]


def test_require_write_filters_read_only_resources() -> None:
    result = compose_capability_resources(
        required_capabilities={"crm.write"},
        resources=[CapabilityResource("kb", "knowledge", frozenset({"crm.write"}), writable=False)],
        require_write=True,
    )
    assert result["complete"] is False
