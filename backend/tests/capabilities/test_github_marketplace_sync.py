from app.capabilities.github_sync import _package_root


def test_package_root_for_codex_and_skill_layouts() -> None:
    assert _package_root("plugins/research/.codex-plugin/plugin.json") == "plugins/research"
    assert _package_root("skills/seo/SKILL.md") == "skills/seo"
    assert _package_root("SKILL.md") == ""


def test_unrelated_file_is_not_package_root() -> None:
    assert _package_root("README.md") is None
