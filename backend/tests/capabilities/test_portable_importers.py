from app.capabilities.importers import import_file_bundle


def test_codex_bundle_detects_skill_and_keeps_references() -> None:
    bundle = import_file_bundle(
        {
            ".codex-plugin/plugin.json": '{"name":"Research pack","license":"MIT","skills":["skills/research"]}',
            "skills/research/SKILL.md": "---\nname: research\ndescription: Research accounts\n---\nFollow evidence.",
            "skills/research/references/checklist.md": "# Checklist",
        }
    )
    assert bundle.inspection.format == "openai_plugin"
    assert bundle.inspection.name == "Research pack"
    assert bundle.resources[0]["kind"] == "reference"


def test_scripts_are_metadata_only() -> None:
    bundle = import_file_bundle(
        {
            "SKILL.md": "---\nname: task\n---\nDo task",
            "scripts/run.py": "print('never direct execute')",
        }
    )
    script = next(r for r in bundle.resources if r["kind"] == "script")
    assert script["content"] is None
    assert script["executable"] is True
