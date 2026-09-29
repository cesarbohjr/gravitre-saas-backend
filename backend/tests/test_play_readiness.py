from app.plays.catalog import PLATFORM_PLAY_TEMPLATES, get_platform_play
from app.plays.contracts import PlayDefinition, VerificationRequirement
from app.plays.readiness import resolve_play_readiness


def test_play_definition_has_no_executor_or_parallel_runtime():
    definition = PlayDefinition(
        key="example",
        name="Example",
        version="1",
        objective="Find and act on an opportunity.",
        workflow_ids=("workflow-existing",),
    )
    payload = definition.as_dict()
    assert payload["workflow_ids"] == ("workflow-existing",)
    assert "execute" not in payload
    assert "steps" not in payload


def test_no_connection_does_not_claim_observe_ready():
    definition = PlayDefinition(
        key="revenue-recovery",
        name="Revenue Recovery",
        version="1",
        objective="Find recoverable revenue.",
        required_connector_groups=(("stripe", "quickbooks"),),
        required_read_action_groups=(("stripe.invoices.list", "quickbooks.invoices.list"),),
    )
    result = resolve_play_readiness(definition, connected_vendors=set())
    assert result.observe_ready is False
    assert result.dependency_status == "EXTERNAL_CONNECTION_REQUIRED"


def test_write_can_reach_approval_maturity_but_not_policy_without_explicit_authorization():
    definition = PlayDefinition(
        key="revenue-recovery",
        name="Revenue Recovery",
        version="1",
        objective="Find recoverable revenue.",
        required_connector_groups=(("hubspot",),),
        required_read_action_groups=(("hubspot.contacts.list",),),
        write_action_groups=(("hubspot.contacts.update",),),
    )
    result = resolve_play_readiness(
        definition,
        connected_vendors={"hubspot"},
        policy_authorized_actions=set(),
    )
    assert result.observe_ready is True
    assert result.recommend_ready is True
    assert result.act_with_approval_ready is True
    assert result.act_within_policy_ready is False


def test_explicit_policy_authorization_is_required_for_act_within_policy():
    definition = PlayDefinition(
        key="customer-rescue",
        name="Customer Rescue",
        version="1",
        objective="Intervene on at-risk customers.",
        required_connector_groups=(("hubspot",),),
        required_read_action_groups=(("hubspot.contacts.list",),),
        write_action_groups=(("hubspot.contacts.update",),),
    )
    result = resolve_play_readiness(
        definition,
        connected_vendors={"hubspot"},
        policy_authorized_actions={"hubspot.contacts.update"},
    )
    assert result.act_within_policy_ready is True


def test_accepted_async_is_not_treated_as_verified_business_result():
    definition = PlayDefinition(
        key="example",
        name="Example",
        version="1",
        objective="Example.",
        verification_requirements=(
            VerificationRequirement(
                action_tool="slack.post_message",
                minimum_mode="source_of_record",
            ),
        ),
    )
    result = resolve_play_readiness(definition, connected_vendors={"slack"})
    row = result.verification[0]
    assert row["adequate_for_verified_result"] is False


def test_initial_play_templates_are_dependency_metadata_only():
    assert {play.key for play in PLATFORM_PLAY_TEMPLATES} == {
        "customer-rescue",
        "revenue-recovery",
        "marketing-performance",
    }
    for play in PLATFORM_PLAY_TEMPLATES:
        payload = play.as_dict()
        assert "steps" not in payload
        assert "executor" not in payload


def test_revenue_recovery_template_keeps_provider_alternatives():
    play = get_platform_play("revenue-recovery")
    assert play is not None
    assert ("stripe", "quickbooks") in play.required_connector_groups
    assert ("stripe.invoices.list", "quickbooks.invoices.list") in play.required_read_action_groups
