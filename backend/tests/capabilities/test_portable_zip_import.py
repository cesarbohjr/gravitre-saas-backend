import io
import zipfile

import pytest

from app.capabilities.importers import import_file_bundle, read_zip_bundle


def _zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_zip_extracts_supported_skill_files() -> None:
    files = read_zip_bundle(
        _zip(
            {
                "skill/SKILL.md": "---\nname: zip-skill\ndescription: ZIP skill\n---\nUse evidence.",
                "skill/references/checklist.md": "# Checklist",
                "skill/assets/logo.png": "ignored binary-shaped extension",
            }
        )
    )
    assert "skill/SKILL.md" in files
    assert "skill/references/checklist.md" in files
    assert "skill/assets/logo.png" not in files


def test_zip_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError, match="path traversal"):
        read_zip_bundle(_zip({"../SKILL.md": "---\nname: unsafe\n---"}))


def test_json_bundle_path_traversal_is_rejected() -> None:
    with pytest.raises(ValueError, match="path traversal"):
        import_file_bundle({"../SKILL.md": "---\nname: unsafe\n---"})
