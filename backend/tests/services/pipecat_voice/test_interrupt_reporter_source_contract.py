"""Structural P0 contracts for Pipecat interruption durability."""
from pathlib import Path

SOURCE = (
    Path(__file__).parents[3]
    / "app/services/pipecat_voice/interrupt_reporter.py"
).read_text(encoding="utf-8")


def test_interruption_frame_moves_before_detached_persistence() -> None:
    push = SOURCE.index("await self.push_frame(frame, direction)", SOURCE.index("# Stop buffered output"))
    persist = SOURCE.index("self._persist_interrupted_detached", push)
    assert push < persist
    assert "await self._persist_interrupted_assistant_text(" not in SOURCE[SOURCE.index("async def process_frame"):push]


def test_exact_update_miss_falls_through_to_idempotent_insert() -> None:
    start = SOURCE.index("def _persist_interrupted_assistant_text_sync")
    section = SOURCE[start:SOURCE.index("async def process_frame", start)]
    assert 'if getattr(updated, "data", None):' in section
    assert "assistant_message_id=message_id or None" in section
