"""Test helpers for speculative adoption.

Every adoption now requires the run's bound state versions to equal the
confirmed turn's, and an unreadable state never matches. Tests about adoption
mechanics (not the version contract itself) use these helpers to stand in for
the state read and the bound versions.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any
from unittest.mock import patch

from app.services.pipecat_voice.speculative_generation import RevisionVersions

MATCHING_VERSIONS = RevisionVersions(
    conversation_id=None,
    pending_task_version="task",
    approval_version="approval",
    context_version="context",
    principal_version="principal",
    prompt_version="prompt",
)


async def _no_task_state(*_a: Any, **_k: Any) -> None:
    return None


@contextmanager
def state_reads_return_nothing() -> Iterator[None]:
    """The task_state read both sides fingerprint returns no state (no DB)."""
    with ExitStack() as stack:
        stack.enter_context(
            patch("app.services.pipecat_voice.speculative_generation.load_revision_task_state", _no_task_state)
        )
        stack.enter_context(patch("app.services.pipecat_voice.cognitive_llm.load_revision_task_state", _no_task_state))
        yield


@contextmanager
def confirmed_turn_sees_matching_versions() -> Iterator[None]:
    """The confirmed turn computes MATCHING_VERSIONS; pair with :func:`adoptable`."""
    with ExitStack() as stack:
        stack.enter_context(state_reads_return_nothing())
        stack.enter_context(
            patch(
                "app.services.pipecat_voice.cognitive_llm.with_turn_inputs",
                lambda _versions, **_k: MATCHING_VERSIONS,
            )
        )
        yield


def adoptable(run: Any) -> Any:
    """Bind a hand-built run to the versions the confirmed turn will see."""
    run.versions = MATCHING_VERSIONS
    return run
