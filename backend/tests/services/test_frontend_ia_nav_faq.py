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
