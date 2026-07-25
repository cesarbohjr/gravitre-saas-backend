"""Structural diff for Meson conversational canvas edits."""
from __future__ import annotations

from app.workflows.definition_diff import diff_builder_graphs, summarize_diff_for_voice


def test_diff_detects_added_and_removed_nodes():
    before = {
        "nodes": [
            {"id": "a", "name": "Start", "type": "source"},
            {"id": "b", "name": "Slack Notification", "type": "connector", "vendor": "slack"},
        ],
        "edges": [{"from_node_id": "a", "to_node_id": "b"}],
    }
    after = {
        "nodes": [
            {"id": "a", "name": "Start", "type": "source"},
            {"id": "c", "name": "Check HubSpot", "type": "connector", "vendor": "hubspot"},
        ],
        "edges": [{"from_node_id": "a", "to_node_id": "c"}],
    }
    diff = diff_builder_graphs(before, after)
    assert diff["available"] is True
    assert diff["summary"]["added"] == 1
    assert diff["summary"]["removed"] == 1
    assert any(n["name"] == "Check HubSpot" for n in diff["added_nodes"])
    assert any(n["name"] == "Slack Notification" for n in diff["removed_nodes"])
    assert "add" in summarize_diff_for_voice(diff)


def test_diff_identical_graphs_unavailable():
    graph = {
        "nodes": [{"id": "a", "name": "Start", "type": "source"}],
        "edges": [],
    }
    diff = diff_builder_graphs(graph, graph)
    assert diff["available"] is False
    assert "No structural" in str(diff.get("note") or "")
