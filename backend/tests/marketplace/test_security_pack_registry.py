from app.outcome_packs.registry import get_pack, list_packs
from app.plays.catalog import get_platform_play
from app.marketplace.marketplace3.certification import certify_outcome_pack


def test_security_blueprint_uses_one_registry_and_cannot_self_certify():
    pack = get_pack("security-operations")
    assert pack is not None
    assert pack.marketplace["status"] == "draft"
    assert not certify_outcome_pack(pack.config).publish_ready
    assert len(pack.config.plays) == 8
    assert len({p.pack_id for p in list_packs()}) == len(list_packs())
    for play in pack.config.plays:
        registered = get_platform_play(play.key)
        assert registered is not None
        assert registered.department == "security"
        assert registered.outcome_metrics == tuple(play.kpi_keys)
