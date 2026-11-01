"""Contract checks for descriptive agent manifests (no implicit tool grants)."""
from app.capabilities.agent_manifest import MANIFESTS, get_agent_manifest, list_agent_manifests


def test_expected_distinct_roles():
    assert set(MANIFESTS) == {"engineering", "qa", "security", "agency"}
    assert len({m.display_name for m in list_agent_manifests()}) == 4


def test_profiles_are_bounded_and_non_authorizing():
    for role, manifest in MANIFESTS.items():
        assert get_agent_manifest(role) is manifest
        assert manifest.requires_human_approval_for_writes is True
        assert manifest.system_guidance.strip()
        assert manifest.capability_tags
        payload = manifest.as_dict()
        assert "allowed_tools" not in payload
        assert "permissions" not in payload
        assert "org_id" not in payload


def test_security_and_qa_guidance():
    assert "IAM" in MANIFESTS["security"].system_guidance
    assert "live" in MANIFESTS["qa"].system_guidance
