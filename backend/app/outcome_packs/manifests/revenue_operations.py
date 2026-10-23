"""Unique #289 RevOps advisory Plays; existing sales/growth packs are preserved."""
from app.marketplace.marketplace3.revenue_operations import build_revenue_operations_outcome_pack_config

def build():
    config = build_revenue_operations_outcome_pack_config()
    config["pack_id"] = "revenue-operations"
    config["department"] = "revenue-operations"
    for play in config["plays"]:
        actions = [step["config"]["action"] for step in play["workflow_steps"] if step.get("type") == "invoke_tool"]
        play["read_action_groups"] = [[action] for action in actions]
        play["required_connector_groups"] = [["hubspot"]]
    return {"marketplace": {"slug": "revenue-operations-3", "title": "Revenue Operations 3.0", "status": "draft", "visibility": "internal"}, "config": config}
