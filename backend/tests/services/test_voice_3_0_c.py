"""3.0-C semantic turn and interrupt taxonomy."""
from __future__ import annotations

from app.services.pipecat_voice.backchannel_classifier import BackchannelClassification
from app.services.semantic_turn import SemanticTurnKind, classify_semantic_turn, looks_semantically_complete
from app.services.voice_interrupt_outcome import FALSE_INTERRUPT, TRUE_INTERRUPT, interrupt_outcome
from app.services.voice_realtime_eval import LANE_A, LANE_B, production_allows_lane, resolve_eval_lane


def test_complete_command_vs_trailing_and():
    assert looks_semantically_complete("show my pipeline this month")
    assert not looks_semantically_complete("the drop was because")


def test_overlap_uh_huh_is_backchannel():
    kind = classify_semantic_turn("uh-huh", overlapping_agent=True, pending_finalize=False)
    assert kind is SemanticTurnKind.BACKCHANNEL


def test_stop_is_true_interrupt():
    assert interrupt_outcome(BackchannelClassification.STOP_COMMAND) == TRUE_INTERRUPT
    assert (
        interrupt_outcome(BackchannelClassification.INTERRUPTION, text="", resolved_by_timeout=True)
        == FALSE_INTERRUPT
    )


def test_production_lane_is_cascade_only():
    assert resolve_eval_lane(None) == LANE_A
    assert production_allows_lane(LANE_A) is True
    assert production_allows_lane(LANE_B) is False
