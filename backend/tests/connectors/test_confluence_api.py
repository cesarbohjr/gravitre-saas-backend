from __future__ import annotations

from app.connectors.confluence import html_to_text, normalize_space


def test_html_to_text_strips_tags():
    assert html_to_text("<p>Hello <strong>world</strong></p>") == "Hello world"


def test_normalize_space():
    space = normalize_space({"id": "99", "key": "ENG", "name": "Engineering"})
    assert space["id"] == "99"
    assert space["key"] == "ENG"
    assert space["name"] == "Engineering"
