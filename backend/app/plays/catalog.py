"""Versioned platform Play templates.

Templates describe outcome intent and dependency requirements only. They do not
contain executable workflow steps and cannot execute actions. A tenant/runtime
instance must bind to canonical workflow ids before execution is possible.
"""
from __future__ import annotations

from app.plays.contracts import PlayDefinition


CUSTOMER_RESCUE = PlayDefinition(
    key="customer-rescue",
    name="Customer Rescue",
    version="1",
    objective="Find customers with credible retention risk, assemble evidence, and prepare an intervention.",
    required_signals=("prediction_generated",),
    required_connector_groups=(
        ("hubspot", "salesforce"),
        ("zendesk", "intercom", "freshdesk"),
    ),
    required_read_action_groups=(
        ("hubspot.contacts.search", "salesforce.accounts.get"),
        ("zendesk.tickets.list", "intercom.conversations.list", "freshdesk.tickets.list"),
    ),
    write_action_groups=(
        ("hubspot.contacts.update", "salesforce.accounts.update"),
        ("zendesk.tickets.update", "intercom.conversations.reply"),
    ),
)


REVENUE_RECOVERY = PlayDefinition(
    key="revenue-recovery",
    name="Revenue Recovery",
    version="1",
    objective="Find stalled or recoverable revenue and assemble source evidence before any action.",
    required_connector_groups=(("stripe", "quickbooks"),),
    required_read_action_groups=(("stripe.invoices.list", "quickbooks.invoices.list"),),
    write_action_groups=(
        ("stripe.subscriptions.update", "quickbooks.invoices.create", "hubspot.deals.update"),
    ),
    outcome_metrics=("arr",),
)


MARKETING_PERFORMANCE = PlayDefinition(
    key="marketing-performance",
    name="Marketing Performance",
    version="1",
    objective="Connect marketing spend and engagement evidence to lead quality and downstream pipeline.",
    required_connector_groups=(
        ("google_ads", "meta_marketing"),
        ("google_analytics",),
    ),
    required_read_action_groups=(
        ("google_ads.reports.performance", "meta_marketing.campaigns.list"),
        ("google_analytics.reports.run",),
    ),
    outcome_metrics=("mql", "cac"),
)


PLATFORM_PLAY_TEMPLATES: tuple[PlayDefinition, ...] = (
    CUSTOMER_RESCUE,
    REVENUE_RECOVERY,
    MARKETING_PERFORMANCE,
)


def get_platform_play(key: str) -> PlayDefinition | None:
    wanted = str(key or "").strip().lower()
    for play in PLATFORM_PLAY_TEMPLATES:
        if play.key == wanted:
            return play
    return None
