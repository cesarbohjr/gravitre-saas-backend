from app.services.extension_bridge_service import (
    _extension_result_urls,
    _project_extension_business_outcome,
)


def test_extension_urls_use_activity_not_outcomes():
    urls = _extension_result_urls("run-123")
    assert urls["outcomeUrl"] == "/runs/run-123"
    assert urls["businessOutcomeUrl"] == "/activity"
    assert "/outcomes/" not in (urls["businessOutcomeUrl"] or "")


def test_extension_projects_business_outcome_for_overlay():
    dto = _project_extension_business_outcome(
        org_id="org-1",
        run_id="run-abc",
        action="apollo.lists.create",
        success=True,
        error_message=None,
        data={
            "message": "Created list",
            "external_url": "https://app.apollo.io/#/lists/1",
            "list_id": "1",
        },
        page_url="https://www.linkedin.com/in/example",
        outcome_effect="created",
    )
    assert dto is not None
    assert dto["projection"] == "business_outcome"
    assert dto["id"] == "run-abc"
    sections = dto["sections"]
    assert "summary" in sections
    assert "evidence" in sections
    assert "verification" in sections
    links = sections["evidence"]["links"]
    assert any("apollo" in (link.get("href") or "").lower() or link.get("kind") == "vendor" for link in links) or len(
        links
    ) >= 1
