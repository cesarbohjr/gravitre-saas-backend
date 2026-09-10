"""Unconnected CRM docs must not rank over a connected CRM action."""
from __future__ import annotations

from app.services.connected_vendor_knowledge_filter import (
    bias_retrieval_query_for_connected_crm,
    filter_competing_crm_knowledge_hits,
    infer_active_crm_vendors,
    is_connector_default_fill_followup,
)


def test_default_fill_followup_is_not_a_knowledge_question():
    assert is_connector_default_fill_followup("Use standard default fields.")
    assert is_connector_default_fill_followup("just use the defaults")
    assert is_connector_default_fill_followup("apply default fields")
    assert not is_connector_default_fill_followup(
        "what are the standard default fields in HubSpot?"
    )
    assert not is_connector_default_fill_followup("Create three HubSpot lists")


def test_hubspot_connected_drops_salesforce_and_siebel_hits():
    hits = [
        {"title": "HubSpot lists and enrollment patterns (Gravitre summary)", "content": "Static lists"},
        {
            "title": "Default Value for Standard Fields in Salesforce",
            "url": "https://trailhead.salesforce.com/example",
            "content": "Set a default value on a standard field",
        },
        {
            "title": "Adding Default Values to Fields",
            "content": "This topic describes how to configure Siebel CRM Desktop",
        },
        {"title": "Neutral ops note", "content": "Retry the previous write with pack defaults."},
    ]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["hubspot", "slack"],
        query="Use standard default fields.",
    )
    titles = [row["title"] for row in kept]
    assert "HubSpot lists and enrollment patterns (Gravitre summary)" in titles
    assert "Neutral ops note" in titles
    assert "Default Value for Standard Fields in Salesforce" not in titles
    assert "Adding Default Values to Fields" not in titles


def test_query_named_hubspot_drops_salesforce_even_if_salesforce_is_connected():
    hits = [
        {"title": "HubSpot list create", "content": "hubspot lists"},
        {"title": "Default Value on Standard Field - Trailhead - Salesforce", "content": "salesforce"},
    ]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["hubspot", "salesforce"],
        query="Create HubSpot lists for MSPs",
    )
    titles = [row["title"] for row in kept]
    assert titles == ["HubSpot list create"]


def test_no_connected_crm_keeps_salesforce_hits():
    hits = [{"title": "Default Value for Standard Fields in Salesforce", "content": "salesforce"}]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["slack"],
        query="What is a standard field?",
    )
    assert len(kept) == 1


def test_bias_appends_hubspot_when_it_is_the_only_connected_crm():
    biased = bias_retrieval_query_for_connected_crm(
        "Use standard default fields.",
        ["hubspot", "slack"],
    )
    assert "HubSpot" in biased
    assert infer_active_crm_vendors(
        "Use standard default fields.",
        connected_integrations=["hubspot"],
    ) == {"hubspot"}


def test_gmail_connected_drops_outlook_hits():
    hits = [
        {"title": "Gmail send defaults", "content": "gmail messages.send"},
        {
            "title": "Set default From address in Outlook",
            "url": "https://support.microsoft.com/outlook",
            "content": "Outlook Microsoft 365 default fields",
        },
    ]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["gmail", "slack"],
        query="Use standard default fields.",
    )
    titles = [row["title"] for row in kept]
    assert "Gmail send defaults" in titles
    assert "Set default From address in Outlook" not in titles


def test_jira_connected_drops_linear_hits():
    hits = [
        {"title": "Create a Jira issue", "content": "jira issues create"},
        {"title": "Linear issue defaults", "content": "linear.app issue template"},
    ]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["jira"],
        query="Create a ticket with the default fields",
    )
    titles = [row["title"] for row in kept]
    assert titles == ["Create a Jira issue"]


def test_slack_only_still_keeps_unrelated_salesforce_docs():
    hits = [{"title": "Default Value for Standard Fields in Salesforce", "content": "salesforce"}]
    kept = filter_competing_crm_knowledge_hits(
        hits,
        connected_integrations=["gmail"],
        query="What is a standard field?",
    )
    assert len(kept) == 1
