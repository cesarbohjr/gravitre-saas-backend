from __future__ import annotations

from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.marketplace.marketplace3.department_portfolio import (
    PACK_SPECS,
    build_department_outcome_pack_config,
    department_portfolio_marketplace3_assets,
)
from app.marketplace.marketplace3.msp_service_desk import (
    build_msp_service_desk_outcome_pack_config,
    msp_service_desk_marketplace3_assets,
)
from app.marketplace.schemas import OutcomePackAssetConfig
from app.plays.catalog import get_platform_play


def _assert_pack_contract(config: dict) -> None:
    parsed = OutcomePackAssetConfig.model_validate(config)
    assert len(parsed.plays) >= 6

    declared_kpis = {row.key for row in parsed.outcome_contract.kpis}
    dashboard_kpis = {row.kpi_key for row in parsed.dashboard.metrics}
    dataset_metrics = {row.key for row in parsed.dataset.metrics}

    assert dashboard_kpis == declared_kpis
    assert declared_kpis <= dataset_metrics

    for play in parsed.plays:
        assert get_platform_play(play.key) is not None, play.key
        assert play.outcome_events
        assert set(play.kpi_keys) <= declared_kpis
        assert play.verification.get("mode") == "source_of_record"
        assert play.verification.get("provider_acceptance_is_terminal") is False

    report = certify_outcome_pack(parsed)
    assert report.publish_ready is True, report.as_dict()
    assert report.level == "production_verified", report.as_dict()
    assert report.unresolved_skill_requirements == []


def test_every_published_department_outcome_pack_is_production_certifiable() -> None:
    for slug in PACK_SPECS:
        _assert_pack_contract(build_department_outcome_pack_config(slug))


def test_msp_service_desk_outcome_pack_is_production_certifiable() -> None:
    _assert_pack_contract(build_msp_service_desk_outcome_pack_config())


def _assert_seeded_outcome_children(assets: list) -> None:
    by_slug = {asset.slug: asset for asset in assets}
    outcomes = [asset for asset in assets if asset.asset_type == "outcome_pack"]
    assert outcomes

    for outcome in outcomes:
        children = [by_slug[slug] for slug in outcome.pack_children]
        types = [child.asset_type for child in children]
        assert types.count("play") >= 6, outcome.slug
        assert types.count("ai_agent") >= 1, outcome.slug
        assert "knowledge_pack" in types, outcome.slug
        assert "dataset_pack" in types, outcome.slug
        assert "dashboard_pack" in types, outcome.slug
        assert "capability_package" in types, outcome.slug
        assert "production-verified" in outcome.tags


def test_seeded_department_outcome_packs_are_complete_composites() -> None:
    _assert_seeded_outcome_children(department_portfolio_marketplace3_assets())


def test_seeded_msp_outcome_pack_is_complete_composite() -> None:
    _assert_seeded_outcome_children(msp_service_desk_marketplace3_assets())
