from app.capabilities.github_marketplace import _package_root


def test_package_root_detects_agent_skill() -> None:
    assert _package_root("skills/seo/SKILL.md") == "skills/seo"


def test_package_root_detects_codex_plugin() -> None:
    assert _package_root("plugins/research/.codex-plugin/plugin.json") == "plugins/research"


def test_unrelated_file_is_not_package_root() -> None:
    assert _package_root("README.md") is None
