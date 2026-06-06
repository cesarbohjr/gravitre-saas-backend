"""STA-106: policy-gated operator auto-execute."""
from __future__ import annotations

from app.operators.services.auto_execute_service import (
    apply_auto_execute_guardrails,
    get_operator_system_prompt,
    step_is_auto_eligible,
)


def test_plan_only_uses_never_auto_execute_prompt():
    prompt = get_operator_system_prompt({"execution_mode": "plan_only"})
    assert "Never auto-execute" in prompt


def test_auto_mode_uses_execution_prompt():
    prompt = get_operator_system_prompt({"execution_mode": "auto_trusted_scopes"})
    assert "automatically" in prompt


def test_trusted_scope_step_eligible():
    operator = {"execution_mode": "auto_trusted_scopes", "auto_execute_trusted_scopes": ["member"]}
    step = {
        "step_type": "execute_workflow",
        "explanation": {
            "executable": True,
            "draft_only": False,
            "admin_required": False,
            "approval_required": False,
            "permissions_required": ["member"],
        },
    }
    assert step_is_auto_eligible(operator, step) is True


def test_apply_auto_execute_clears_confirmation_for_trusted_step():
    operator = {"execution_mode": "auto_trusted_scopes", "auto_execute_trusted_scopes": ["member"]}
    plan = {
        "steps": [
            {
                "id": "s1",
                "step_type": "execute_workflow",
                "explanation": {
                    "executable": True,
                    "draft_only": False,
                    "admin_required": False,
                    "approval_required": False,
                    "permissions_required": ["member"],
                    "confirmation_required": True,
                },
            }
        ],
        "guardrails": {"execution_restrictions": []},
    }
    updated = apply_auto_execute_guardrails(plan, operator)
    assert updated["steps"][0]["explanation"]["confirmation_required"] is False
