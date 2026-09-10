from app.services.user_facing_activity import (
    SAFE_STATUS_FALLBACK,
    looks_like_internal_status,
    sanitize_user_activity_label,
    specific_connector_status,
    user_status_payload,
)


MUTATION_UNMAPPED = "TotallyNewUnmappedKernel.info"


def test_kernel_pre_act_maps_to_human_copy():
    assert (
        sanitize_user_activity_label("CognitiveTurnKernel pre-ACT complete")
        == "Reviewing context and memory"
    )


def test_mutation_unmapped_internal_fails_closed():
    assert looks_like_internal_status(MUTATION_UNMAPPED) is True
    assert sanitize_user_activity_label(MUTATION_UNMAPPED) == SAFE_STATUS_FALLBACK
    payload = user_status_payload(MUTATION_UNMAPPED)
    assert payload["label"] == SAFE_STATUS_FALLBACK
    assert payload["internal"] is True


def test_snake_case_codes_fail_closed():
    assert sanitize_user_activity_label("write_approval_required") == SAFE_STATUS_FALLBACK
    assert sanitize_user_activity_label("orphan_plan_unclear_ask") == "Waiting for your direction"


def test_specific_connector_status():
    assert specific_connector_status(["hubspot"]) == "Checking your Hubspot account"
    assert "HubSpot" in (specific_connector_status(["HubSpot", "Salesforce"]) or "")


def test_connected_tools_label_uses_real_connectors():
    assert (
        sanitize_user_activity_label(
            "Reviewing connected systems and knowledge",
            connectors=["hubspot"],
        )
        == "Checking your Hubspot account"
    )


def test_running_prefix_is_stripped():
    assert sanitize_user_activity_label("Running: Search contacts in Apollo") == "Search contacts in Apollo"


def test_human_copy_passes_through():
    assert sanitize_user_activity_label("Searching your HubSpot contacts") == "Searching your HubSpot contacts"
