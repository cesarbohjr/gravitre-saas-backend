from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ROUTER=(ROOT/"app"/"routers"/"training.py").read_text()

def test_workflow_agent_service_is_not_shadowed_by_route_handler():
    assert "list_workflow_agents as list_training_workflow_agents" in ROUTER
    assert 'list_training_workflow_agents(client, org_id)' in ROUTER
