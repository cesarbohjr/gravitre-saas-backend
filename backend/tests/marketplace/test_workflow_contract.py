from app.marketplace.workflow_contract import resolve_step_agent_seeds, steps_to_rich_contract
from app.marketplace.workflows.msp_enrichment_workflow import build_msp_enrichment_workflow_steps


def test_steps_to_rich_contract_preserves_actions_and_tasks():
    steps = build_msp_enrichment_workflow_steps()
    nodes, edges = steps_to_rich_contract(steps)
    assert len(nodes) == len(steps)
    assert len(edges) == len(steps) - 1
    apollo = next(n for n in nodes if n["id"] == "apollo_lists")
    assert apollo["type"] == "connector"
    assert apollo["config"]["action"] == "apollo.lists.list"
    agent = next(n for n in nodes if n["id"] == "prepare_clay_batch")
    assert agent["type"] == "agent"
    add = next(n for n in nodes if n["id"] == "apollo_list_add")
    assert add["type"] == "connector"
    assert add["config"]["action"] == "apollo.lists.add"


def test_resolve_step_agent_seeds_binds_uuid():
    steps = resolve_step_agent_seeds(
        [
            {
                "id": "a",
                "name": "Agent",
                "type": "agent",
                "metadata": {
                    "agent_seed": "agent:lead-enrichment-coordinator",
                    "task": "Do work",
                },
            }
        ],
        agent_ids_by_seed={"agent:lead-enrichment-coordinator": "uuid-1"},
    )
    assert steps[0]["metadata"]["agent_id"] == "uuid-1"
    assert "agent_seed" not in steps[0]["metadata"]
