"""MKT-PACK-AUDIT 5.1: workflow step handoff resolution at install."""
from __future__ import annotations

from app.marketplace.service import _resolve_workflow_steps


def test_resolve_workflow_steps_maps_next_agent_seed_to_id():
    agent_ids = {
        "agent:product-icp-strategist": "agent-icp",
        "agent:content-writer": "agent-writer",
        "agent:marketing-designer": "agent-designer",
        "agent:marketing-ops-coordinator": "agent-ops",
    }
    steps = [
        {
            "id": "icp_content",
            "name": "ICP strategy and content draft",
            "type": "agent",
            "metadata": {
                "agent_seed": "agent:product-icp-strategist",
                "next_agent_seed": "agent:content-writer",
                "task": "Define ICP focus.",
                "receiver_task": "Draft copy.",
            },
        }
    ]

    resolved = _resolve_workflow_steps(steps, agent_ids=agent_ids, connector_ids={})

    metadata = resolved[0]["metadata"]
    assert metadata["agent_id"] == "agent-icp"
    assert metadata["next_agent_id"] == "agent-writer"
    assert "next_agent_seed" not in metadata
    assert "agent_seed" not in metadata
