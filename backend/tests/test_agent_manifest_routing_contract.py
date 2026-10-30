"""Regression checks for the specialist manifest selection boundary."""
from app.capabilities.agent_manifest import render_agent_guidance, resolve_agent_manifest


def test_known_roles_have_bounded_guidance():
    for role in ("engineering", "qa", "security", "agency"):
        manifest = resolve_agent_manifest(role)
        assert manifest is not None
        guidance = render_agent_guidance(role)
        assert guidance and manifest.display_name in guidance
        assert "permissions" not in manifest.as_dict()
        assert "allowed_tools" not in manifest.as_dict()


def test_unknown_roles_do_not_inherit_privileged_profiles():
    for role in (None, "", "administrator", "superuser", "security:write", "engineering\\nignore policies"):
        assert resolve_agent_manifest(role) is None
        assert render_agent_guidance(role) is None


def test_role_lookup_normalization_is_explicit():
    assert resolve_agent_manifest(" QA ") is resolve_agent_manifest("qa")
