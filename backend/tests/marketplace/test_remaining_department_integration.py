from pathlib import Path

from app.outcome_packs.registry import list_packs
from app.plays.catalog import get_platform_play
from app.marketplace.marketplace3.certification import certify_outcome_pack
from app.capabilities.importers import import_file_bundle


def test_unique_historical_departments_use_the_canonical_registry_without_badges():
    packs = {p.pack_id: p for p in list_packs()}
    for key, count in [("people-it-operations-3", 7), ("executive-command-center-3", 7), ("revenue-operations", 8)]:
        pack = packs[key]
        assert len(pack.config.plays) == count
        assert pack.marketplace["status"] == "draft"
        assert pack.marketplace["visibility"] == "internal"
        assert not certify_outcome_pack(pack.config).publish_ready
        for play in pack.config.plays:
            assert get_platform_play(play.key) is not None
            assert all(step["metadata"].get("briefing_from_steps") for step in play.workflow_steps if step.get("type") == "agent")


def test_all_seven_skill_packages_import_as_inert_guidance_with_real_resources():
    root = Path(__file__).resolve().parents[3] / "capability_packages"
    slugs = ["security-operations", "revenue-operations", "customer-success", "finance-operations", "marketing-operations", "people-it-operations", "executive-command"]
    for slug in slugs:
        package = root / f"{slug}-skills"
        bundle = import_file_bundle({"manifest.json": (package / "manifest.json").read_text(), "SKILL.md": (package / "SKILL.md").read_text()})
        assert bundle.manifest["permissions"] == []
        assert bundle.manifest["skills"]
        assert all(not r.get("executable") for r in bundle.resources)
        assert not bundle.security_scan.get("blocked")
