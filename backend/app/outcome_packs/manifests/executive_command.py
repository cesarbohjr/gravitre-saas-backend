"""Historical unique department requirements on the canonical pack runtime."""
from app.outcome_packs.historical_departments import build_department_outcome_pack_config

def build():
    config = build_department_outcome_pack_config("executive-command-center-3")
    config["pack_id"] = "executive-command-center-3"
    config["department"] = "executive"
    for play in config["plays"]:
        actions = [step["config"]["action"] for step in play["workflow_steps"] if step.get("type") == "invoke_tool"]
        play["read_action_groups"] = [[action] for action in actions]
        play["required_connector_groups"] = [[action.split(".")[0]] for action in actions]
    return {"marketplace": {"slug": "executive-command-center-3", "title": "Executive Command Center 3.0", "status": "draft", "visibility": "internal"}, "config": config}
