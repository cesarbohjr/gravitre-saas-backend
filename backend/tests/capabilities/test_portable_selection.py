from app.capabilities.selection import select_relevant_packages


def test_selects_relevant_installed_skill_without_loading_all_packages() -> None:
    packages = [
        {
            "name": "SEO analyst",
            "description": "Audit search rankings, keywords and backlinks",
            "package_format": "agent_skill",
            "status": "installed",
            "inspection": {"components": [{"kind": "skill", "name": "seo-audit"}]},
        },
        {
            "name": "Finance",
            "description": "Budget and forecast analysis",
            "package_format": "agent_skill",
            "status": "installed",
            "inspection": {"components": [{"kind": "skill", "name": "forecast"}]},
        },
    ]
    selected = select_relevant_packages("Audit our SEO backlinks and rankings", packages)
    assert [p["name"] for p in selected] == ["SEO analyst"]


def test_quarantined_package_is_not_selected() -> None:
    selected = select_relevant_packages(
        "send CRM email",
        [{"name": "CRM", "description": "send CRM email", "status": "quarantined", "inspection": {}}],
    )
    assert selected == []
