from __future__ import annotations

from app.connectors.notion import block_to_lines, page_title


def test_block_to_lines_heading():
    block = {
        "type": "heading_1",
        "heading_1": {"rich_text": [{"plain_text": "Playbook"}]},
    }
    assert block_to_lines(block) == ["# Playbook"]


def test_block_to_lines_todo():
    block = {
        "type": "to_do",
        "to_do": {"rich_text": [{"plain_text": "Fix deploy"}], "checked": True},
    }
    assert block_to_lines(block) == ["[x] Fix deploy"]


def test_page_title_from_properties():
    page = {
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "Engineering SOP"}],
            }
        }
    }
    assert page_title(page) == "Engineering SOP"
