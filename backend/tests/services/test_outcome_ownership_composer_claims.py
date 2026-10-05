from __future__ import annotations

import pytest

from app.services.response_composer import compose_user_reply, has_completion_claim


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "claim",
    [
        "Done.",
        "I completed the task.",
        "The contact has been created.",
        "All set.",
        "I have created the list.",
        "The workflow finished.",
    ],
)
async def test_composer_blocks_completion_paraphrases_without_verification(claim: str) -> None:
    text = await compose_user_reply(
        {"success": True, "execution_verified": False, "data": {}},
        kind="success",
        draft=claim,
        compose_fn=lambda **_: _return(claim),
    )
    assert not has_completion_claim(text)


@pytest.mark.asyncio
async def test_composer_allows_completion_when_execution_is_verified() -> None:
    claim = "Done. The contact has been created."
    text = await compose_user_reply(
        {"success": True, "execution_verified": True, "data": {}},
        kind="success",
        draft=claim,
        compose_fn=lambda **_: _return(claim),
    )
    assert "created" in text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [
        "Your completed deals are listed below.",
        "The onboarding sequence has three finished steps and two open ones.",
    ],
)
async def test_composer_leaves_answer_turns_alone(answer: str) -> None:
    # No action ran on this turn, so "completed" describes data, not an outcome.
    text = await compose_user_reply(
        {"success": True, "data": {"rows": 12}},
        kind="success",
        draft=answer,
        compose_fn=lambda **_: _return(answer),
    )
    assert text == answer


@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("I stopped before it completed.", False),
        ("It is not done yet.", False),
        ("I'll tell you once it's complete.", False),
        ("The contact has been updated.", True),
        ("That went through.", True),
    ],
)
def test_completion_claim_detector_handles_negation(text: str, claim: bool) -> None:
    assert has_completion_claim(text) is claim


async def _return(value: str) -> str:
    return value
