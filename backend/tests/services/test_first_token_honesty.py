"""Phase F2 first-token honesty: Done. only after a verified write."""

from app.services.first_token_honesty import (
    STAGE_COMPOSE,
    STAGE_PLAN,
    STAGE_TOOL,
    envelope_allows_completion_claim,
    envelope_from_tool_results,
    is_standalone_done,
    looks_like_tool_payload,
    reject_premature_done,
    status_for_stage,
)


def test_stage_labels_are_operator_copy() -> None:
    assert "Understanding" in status_for_stage(STAGE_PLAN)
    assert "tools" in status_for_stage(STAGE_TOOL).lower()
    assert "Composing" in status_for_stage(STAGE_COMPOSE)


def test_completion_claim_requires_verified_write() -> None:
    assert envelope_allows_completion_claim({"success": True}) is False
    assert envelope_allows_completion_claim({"success": True, "data": {"text": "ok"}}) is False
    assert envelope_allows_completion_claim({"success": True, "execution_verified": True}) is True
    assert (
        envelope_allows_completion_claim(
            {"success": True, "data": {"execution_verified": True}}
        )
        is True
    )
    assert (
        envelope_allows_completion_claim(
            {
                "success": True,
                "execution_verified": True,
                "pending_task": {"status": "awaiting_confirm"},
            }
        )
        is False
    )
    assert envelope_allows_completion_claim({"success": False, "execution_verified": True}) is False


def test_reject_premature_done() -> None:
    fallback = "I have that. What should we do with it?"
    assert reject_premature_done("Done.", {"success": True}, fallback=fallback) == fallback
    assert reject_premature_done("done", {"success": True}, fallback=fallback) == fallback
    assert (
        reject_premature_done("Done.", {"success": True, "execution_verified": True}, fallback=fallback)
        == "Done."
    )
    assert (
        reject_premature_done("Created the Apollo list.", {"success": True}, fallback=fallback)
        == "Created the Apollo list."
    )
    assert is_standalone_done("Done.") is True
    assert is_standalone_done("Done. List created.") is False


def test_tool_json_is_not_operator_prose() -> None:
    assert looks_like_tool_payload('{"success": true, "data": {"id": "1"}}') is True
    assert looks_like_tool_payload('{"error_code": "tool_error", "success": false}') is True
    assert looks_like_tool_payload('{"success":') is True
    assert looks_like_tool_payload("Created the Apollo list.") is False
    env = envelope_from_tool_results(
        [{"name": "apollo.lists.create", "output": {"success": True, "data": {"name": "Q3"}}}]
    )
    assert env is not None
    assert env["success"] is True
