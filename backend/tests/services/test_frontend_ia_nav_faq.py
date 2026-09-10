from app.services.frontend_ia_nav_faq import match_frontend_ia_nav_faq


def test_activity_nav_faq():
    hit = match_frontend_ia_nav_faq(
        "Where do I look up completed workflow work and failure alerts in the app navigation?"
    )
    assert hit is not None
    assert hit["hub"] == "activity"
    assert "/activity" in hit["answer"]


def test_settings_nav_faq():
    hit = match_frontend_ia_nav_faq(
        "In the Gravitre sidebar, which primary nav item holds Enterprise, Federation, and Environments?"
    )
    assert hit is not None
    assert hit["hub"] == "settings"
    assert "Settings" in hit["answer"]


def test_intelligence_nav_faq():
    hit = match_frontend_ia_nav_faq(
        "Which primary hub holds operational metrics, ROI reports, and learning signals?"
    )
    assert hit is not None
    assert hit["hub"] == "intelligence"
    assert "/intelligence" in hit["answer"]


def test_unrelated_message_is_none():
    assert match_frontend_ia_nav_faq("Send an email to sales@example.com") is None


def test_google_ads_campaign_setup_is_not_settings_faq():
    """Regression: operator tasks mentioning enterprise + where must reach tools."""
    message = """
    I have a Google Ads campaign strategy ready to go live. Set it up in
    Google Ads exactly as specified below, and don't execute anything
    without my approval first.

    Create four campaigns:

    1. RevOps / Sales Ops — 30% budget weight.
    2. IT / Security Ops — 30% budget weight. Ad groups include
       "shadow AI in the enterprise" and "enterprise AI agent management platform".
    3. DevOps / Engineering Leaders — 20% budget weight.
    4. Customer Support Ops — 20% budget weight, including
       "enterprise support automation software".

    Before you create anything: check that my Google Ads account is
    actually connected and has the right access, confirm you can see my
    current account structure so we're not creating duplicates, and show me
    the complete plan for what you're about to create, campaign by campaign,
    before asking me to approve it.

    Once I approve, go ahead and create it, and once it's live, show me
    where I can verify each campaign actually exists in my real Google Ads
    account, not just that Gravitre says it worked.
    """
    assert match_frontend_ia_nav_faq(message) is None


def test_enterprise_where_without_nav_is_not_settings_faq():
    assert (
        match_frontend_ia_nav_faq(
            "Show me where I can verify the enterprise AI agent campaign in Google Ads."
        )
        is None
    )


def test_operator_google_ads_hints_never_match_faq():
    assert (
        match_frontend_ia_nav_faq(
            "Set it up in Google Ads. Create four campaigns for enterprise "
            "security, then show me where I can verify them."
        )
        is None
    )
