from app.services.operator_task_intent import (
    looks_like_operator_task,
    should_keep_full_reasoning_for_spoken,
    should_skip_unified_live_guards,
    use_spoken_lite_path,
)
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    CONNECTOR_LOOKUP,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    MULTI_PARAM_WRITE,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)


def test_google_ads_brief_is_operator_task() -> None:
    assert looks_like_operator_task(GOOGLE_ADS_CAMPAIGN_BRIEF)
    assert should_keep_full_reasoning_for_spoken(GOOGLE_ADS_CAMPAIGN_BRIEF)


def test_rule_10_hubspot_vent_is_not_operator_task() -> None:
    assert not looks_like_operator_task("ugh this HubSpot connector is being annoying")


def test_greeting_is_not_operator_task() -> None:
    assert not looks_like_operator_task("hey, how's it going")
    assert not looks_like_operator_task(AMBIGUOUS_CLARIFY)


def test_connector_lookup_and_list_create_are_operator_tasks() -> None:
    assert looks_like_operator_task(CONNECTOR_LOOKUP)
    assert looks_like_operator_task(MULTI_PARAM_WRITE)
    assert looks_like_operator_task("In Apollo, create a contact list.")


def test_spoken_lite_path_never_hijacks_operator_tasks() -> None:
    assert use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message="hey, how's it going",
    )
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message=GOOGLE_ADS_CAMPAIGN_BRIEF,
    )
    assert not use_spoken_lite_path(
        spoken_mode=True,
        routing_tier="simple",
        message=SEO_PLUS_GOOGLE_ADS,
    )
    assert not use_spoken_lite_path(
        spoken_mode=False,
        routing_tier="simple",
        message="hey, how's it going",
    )


def test_spoken_live_guards_stay_on_for_operator_tasks() -> None:
    assert should_skip_unified_live_guards(
        spoken_mode=True,
        reasoning_depth="conversational",
        has_pending=False,
        message="hey, how's it going",
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=True,
        reasoning_depth="conversational",
        has_pending=False,
        message=GOOGLE_ADS_CAMPAIGN_BRIEF,
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=True,
        reasoning_depth="full",
        has_pending=False,
        message="hey, how's it going",
    )
    assert not should_skip_unified_live_guards(
        spoken_mode=False,
        reasoning_depth="conversational",
        has_pending=False,
        message="hey, how's it going",
    )
    assert looks_like_operator_task(VENTING_PLUS_GOOGLE_ADS)
