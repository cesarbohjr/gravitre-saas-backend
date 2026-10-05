from __future__ import annotations

import pytest

from app.services.response_composer import compose_user_reply


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
    assert text == "The action was executed, but I have not verified the requested outcome yet."


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


async def _return(value: str) -> str:
    return value
