from unittest.mock import patch

from app.capabilities.runtime import build_portable_skill_context


def test_runtime_loads_skill_text_but_never_script_content() -> None:
    packages = [
        {
            "id": "pkg-1",
            "name": "CRM playbook",
            "description": "CRM follow-up and sales outreach",
            "package_format": "agent_skill",
            "status": "installed",
            "inspection": {},
        }
    ]
    resources = [
        {"path": "SKILL.md", "kind": "reference", "content": "Always verify CRM data.", "executable": False},
        {"path": "scripts/run.py", "kind": "script", "content": "danger()", "executable": True},
    ]
    with (
        patch("app.capabilities.runtime.list_packages", return_value=packages),
        patch("app.capabilities.runtime.list_package_resources", return_value=resources),
    ):
        block, meta = build_portable_skill_context(
            object(), org_id="org-1", prompt="follow up in CRM"
        )
    assert "Always verify CRM data." in block
    assert "danger()" not in block
    assert meta["scriptsExecuted"] is False
