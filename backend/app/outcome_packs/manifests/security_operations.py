"""Security Operations blueprint on the canonical pack/Play/metric registry.

No publication, pricing, production badge or autonomous containment is implied.
"""
from typing import Any


def build() -> dict[str, Any]:
    from app.marketplace.marketplace3.security_operations import build_security_operations_outcome_pack_config
    config = build_security_operations_outcome_pack_config()
    config["pack_id"] = "security-operations"
    config["department"] = "security"
    # The historical pack uses workflow steps; expose its read contracts to the
    # shared Play registry without inventing a second catalog or executor.
    for play in config["plays"]:
        actions = [step["config"]["action"] for step in play["workflow_steps"]
                   if step.get("type") == "invoke_tool"]
        play["read_action_groups"] = [[action] for action in actions]
        play["required_connector_groups"] = [["okta"]]
    return {"marketplace": {"slug": "security-operations-3", "title": "Security Operations 3.0",
                            "status": "draft", "visibility": "internal"}, "config": config}
