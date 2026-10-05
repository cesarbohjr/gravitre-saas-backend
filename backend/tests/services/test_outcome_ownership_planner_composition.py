from app.services.cognitive_planner import CognitivePlanner


def test_planner_composes_compound_objective_from_runtime_resources() -> None:
    state = {
        "objective_contract": {
            "objective": "Research stalled accounts and update CRM",
            "required_capabilities": ["crm.write", "account.research"],
            "requires_write": False,
        },
        "capability_resources": [
            {
                "id": "hubspot",
                "kind": "connector",
                "capabilities": ["crm.write"],
                "connected": True,
                "writable": True,
                "verified": True,
            },
            {
                "id": "web",
                "kind": "internet",
                "capabilities": ["account.research"],
                "connected": True,
                "verified": True,
            },
        ],
    }
    plan = CognitivePlanner().plan(
        "Research stalled accounts and update CRM",
        state,
        {},
        {},
    )
    assert plan["capability_composition"]["complete"] is True
    assert {r["kind"] for r in plan["capability_composition"]["selected"]} == {"connector", "internet"}


def test_planner_exposes_missing_compound_capability() -> None:
    state = {
        "objective_contract": {
            "required_capabilities": ["crm.write", "account.research"],
        },
        "capability_resources": [
            {"id": "hubspot", "kind": "connector", "capabilities": ["crm.write"], "writable": True}
        ],
    }
    plan = CognitivePlanner().plan("Research and update", state, {}, {})
    assert plan["capability_composition"]["complete"] is False
    assert plan["capability_composition"]["missing_capabilities"] == ["account.research"]
