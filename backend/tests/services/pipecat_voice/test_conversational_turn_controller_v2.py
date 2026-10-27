"""Regression contract for the feature-gated duplex turn policy."""
import pytest

from app.services.pipecat_voice.conversational_turn_controller_v2 import (
    ConversationalTurnControllerV2,
    TurnAction,
)


@pytest.mark.parametrize(
    ("utterance", "action"),
    [
        ("stop talking, keep working", TurnAction.SPEECH_ONLY_STOP),
        ("hold on", TurnAction.PAUSE),
        ("cancel that", TurnAction.INTERRUPT),
        ("use last quarter instead", TurnAction.INTERRUPT),
        ("right", TurnAction.BACKCHANNEL),
    ],
)
def test_overlapping_speech_decisions(utterance, action):
    decision = ConversationalTurnControllerV2().decide(
        utterance, bot_speaking=True, final=True
    )
    assert decision.action is action


def test_acknowledgement_does_not_cancel_thinking_work():
    decision = ConversationalTurnControllerV2().decide(
        "right", bot_speaking=False, assistant_thinking=True, final=True
    )
    assert decision.action is TurnAction.BACKCHANNEL


def test_expected_answer_is_not_discarded_as_backchannel():
    decision = ConversationalTurnControllerV2().decide(
        "right", bot_speaking=True, expects_answer=True, final=True
    )
    assert decision.action is TurnAction.INTERRUPT


def test_semantic_wait_is_bounded():
    controller = ConversationalTurnControllerV2()
    text = "I need the report for"
    assert controller.hold_incomplete_interim(text, elapsed_s=0.1, max_wait_s=1.8)
    assert not controller.hold_incomplete_interim(text, elapsed_s=1.8, max_wait_s=1.8)


def test_explicit_speech_stop_preempts_incomplete_wait():
    decision = ConversationalTurnControllerV2().decide(
        "stop talking, keep working", bot_speaking=True, final=False
    )
    assert decision.action is TurnAction.SPEECH_ONLY_STOP
