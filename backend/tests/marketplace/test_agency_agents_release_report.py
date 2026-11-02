"""Release reporting must never confuse candidate approval with deployment."""
from app.marketplace.agency_agents_release_report import build_release_review


def test_all_profiles_get_individual_release_status():
    report = build_release_review()
    assert report["profile_count"] == 283
    assert report["division_count"] == 18
    assert len({r["slug"] for r in report["roles"]}) == 283
    assert report["production_publication_authorized"] is False
    assert all(r["deployment_status"] == "not_verified" for r in report["roles"])
    assert all(r["certification_status"] == "not_run" for r in report["roles"])
    assert sum(report["review_status_counts"].values()) == 283


def test_exclusions_remain_excluded_and_reviewable():
    report = build_release_review()
    excluded = [r for r in report["roles"] if r["disposition"] == "exclude"]
    assert len(excluded) == 1
    assert excluded[0]["review_status"] == "excluded_pending_review"
    assert excluded[0]["target_agent"] is None


def test_report_is_reproducible():
    assert build_release_review() == build_release_review()


def test_marketplace_staging_is_non_publishable_and_complete():
    from app.marketplace.agency_agents_release_report import build_marketplace_staging_plan
    report = build_release_review()
    plan = build_marketplace_staging_plan()
    assert not plan["publication_enabled"]
    assert plan["source_commit"] == report["source_commit"]
    assert plan["preview_count"] == sum(
        r["disposition"] == "marketplace_agent" for r in report["roles"]
    )
    assert all(row["preview_only"] and not row["publishable"] for row in plan["previews"])
    assert all(row["required_connectors"] == [] for row in plan["previews"])
