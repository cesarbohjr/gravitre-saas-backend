"""Phase 2 connector route keys — import-safe (no executor dependencies)."""
from __future__ import annotations

PHASE2_VENDORS = frozenset({"linear", "gitlab", "shopify", "paypal", "brevo", "meta_marketing"})

PHASE2_ROUTES: frozenset[str] = frozenset(
    {
        "linear.issues.list",
        "linear.issues.get",
        "linear.issues.create",
        "linear.issues.update",
        "linear.issues.search",
        "gitlab.projects.list",
        "gitlab.issues.list",
        "gitlab.issues.create",
        "gitlab.merge_requests.create",
        "gitlab.merge_requests.list",
        "shopify.products.list",
        "shopify.orders.list",
        "shopify.products.create",
        "shopify.orders.update",
        "shopify.customers.list",
        "paypal.payments.list",
        "paypal.orders.get",
        "paypal.refunds.create",
        "paypal.payouts.create",
        "paypal.disputes.list",
        "brevo.contacts.list",
        "brevo.campaigns.list",
        "brevo.email.send",
        "brevo.contacts.create",
        "brevo.contacts.update",
        "meta_marketing.campaigns.list",
        "meta_marketing.adsets.list",
        "meta_marketing.campaigns.create",
        "meta_marketing.campaigns.update",
        "meta_marketing.adsets.update",
    }
)
