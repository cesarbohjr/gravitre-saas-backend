"""Historical unique department requirements on the canonical pack runtime."""
from app.outcome_packs.historical_departments import build_department_outcome_pack_config

def build():
    config = build_department_outcome_pack_config("people-it-operations-3")
    config["pack_id"] = "people-it-operations-3"
    config["department"] = "people-it"
    for play in config["plays"]:
        actions = [step["config"]["action"] for step in play["workflow_steps"] if step.get("type") == "invoke_tool"]
        play["read_action_groups"] = [[action] for action in actions]
        play["required_connector_groups"] = [[action.split(".")[0]] for action in actions]
    return {"marketplace": {"slug": "people-it-operations-3", "title": "People & IT Operations 3.0", "status": "draft", "visibility": "internal"}, "config": config}
