"""Does markdown still reach the browser on a voice turn?

Measured in production 2026-09-08: ``assistant_text`` deltas carried raw
markdown — 12 ``**`` pairs on a tool-using turn, 6 on an orchestration turn
(``"I planned a **2-step orchestration**:"``,
``"Source: **assistant_workflow_runs**"``). These tests pin the streaming
behaviour that fixes it, including the case that makes naive per-delta stripping
wrong: a marker split across two deltas.
"""
from __future__ import annotations

import pytest

from app.services.pipecat_voice.spoken_stream_filter import SpokenMarkdownStreamFilter
from app.services.voice_session_service import normalize_spoken_text


def _stream(deltas: list[str]) -> str:
    filt = SpokenMarkdownStreamFilter()
    return "".join(filt.feed(d) for d in deltas) + filt.flush()


class TestObservedProductionStrings:
    def test_orchestration_plan_loses_all_markdown(self):
        out = _stream(["I planned a **2-step orchestration**:"])
        assert out == "I planned a 2-step orchestration:"
        assert "*" not in out

    def test_source_citation_keeps_identifier_underscores(self):
        """assistant_workflow_runs must not become assistantworkflowruns."""
        out = _stream(["Source: **assistant_workflow_runs**."])
        assert out == "Source: assistant_workflow_runs."

    def test_single_asterisk_italics_removed(self):
        out = _stream(["step 2 — *skipped* (no action matched)"])
        assert "*" not in out
        assert "skipped" in out

    def test_numbered_list_with_bold_label(self):
        out = _stream(["1. **Search people** (read, auto-run)"])
        assert out == "Search people (read, auto-run)"

    def test_full_tool_turn_reply_has_no_markdown(self):
        reply = (
            "Yes — there is a completed run today.\n"
            "- The latest run shown is **completed** at **11:33 UTC**.\n"
            "- Source: **assistant_workflow_runs**.\n"
        )
        out = _stream([reply])
        assert "**" not in out
        assert "*" not in out
        assert "completed" in out and "11:33 UTC" in out


class TestMarkersSplitAcrossDeltas:
    """The reason per-delta stripping is not sufficient."""

    def test_bold_marker_split_between_deltas(self):
        assert _stream(["Status is **comp", "leted** now."]) == "Status is completed now."

    def test_marker_characters_arrive_one_at_a_time(self):
        deltas = list("The run is **done** already.")
        assert _stream(deltas) == "The run is done already."

    def test_no_orphan_asterisk_is_ever_emitted_mid_stream(self):
        filt = SpokenMarkdownStreamFilter()
        emitted = []
        for delta in ["Value ", "**", "42", "**", " confirmed."]:
            emitted.append(filt.feed(delta))
        emitted.append(filt.flush())
        for piece in emitted:
            assert "*" not in piece, f"orphan marker leaked in {piece!r}"
        assert "".join(emitted) == "Value 42 confirmed."

    def test_link_split_across_deltas(self):
        assert _stream(["See [the run](https://x.test/1", ") for detail."]) == (
            "See the run for detail."
        )

    def test_backtick_code_span_split(self):
        assert _stream(["Field `state", "_name` is set."]) == "Field state_name is set."


class TestStreamingSafety:
    def test_words_never_glue_together(self):
        out = _stream(["Hello ", "there ", "friend."])
        assert out == "Hello there friend."

    def test_unclosed_construct_is_still_emitted_on_flush(self):
        """A model that opens emphasis and never closes it must not lose text."""
        filt = SpokenMarkdownStreamFilter()
        held = filt.feed("Almost *done")
        tail = filt.flush()
        assert "done" in (held + tail)
        assert "*" not in (held + tail)

    def test_plain_text_passes_through_unchanged(self):
        text = "The sync finished at 11:33 and nothing failed."
        assert _stream([text]) == text

    def test_newlines_preserved_for_incremental_rendering(self):
        assert _stream(["line one\nline two"]) == "line one\nline two"

    def test_list_marker_stripped_only_at_line_start(self):
        """A hyphen mid-sentence is content, not a bullet."""
        out = _stream(["- first item\nrange is 5 - 10\n"])
        assert "first item" in out
        assert "5 - 10" in out

    def test_list_marker_stripped_when_newline_and_marker_split(self):
        out = _stream(["done\n", "- next item"])
        assert out == "done\nnext item"

    def test_reset_clears_held_state(self):
        filt = SpokenMarkdownStreamFilter()
        filt.feed("held *open")
        filt.reset()
        assert filt.pending == ""
        assert filt.feed("fresh start") == "fresh start"

    def test_math_asterisk_is_not_spoken_as_a_marker(self):
        out = _stream(["compute 3 * 4 now"])
        assert "*" not in out


class TestAgreementWithTtsNormalizer:
    """Both paths must agree on what a marker is, or audio and text diverge."""

    @pytest.mark.parametrize(
        "source",
        [
            "Reply **yes** to continue.",
            "step *skipped* here",
            "Source: **assistant_workflow_runs**",
            "use `state_name` field",
        ],
    )
    def test_no_markdown_survives_either_path(self, source: str):
        assert "*" not in _stream([source])
        assert "*" not in normalize_spoken_text(source)
        assert "`" not in _stream([source])
        assert "`" not in normalize_spoken_text(source)

    def test_identifier_underscores_survive_both_paths(self):
        source = "Source: **assistant_workflow_runs**."
        assert "assistant_workflow_runs" in _stream([source])
        assert "assistant_workflow_runs" in normalize_spoken_text(source)


class TestWiredIntoVoicePath:
    def test_client_deltas_go_through_the_filter(self):
        """A filter that exists but is not applied fixes nothing."""
        import inspect

        from app.services.pipecat_voice import cognitive_llm

        source = inspect.getsource(cognitive_llm)
        assert "SpokenMarkdownStreamFilter()" in source
        assert "client_text_filter.feed(delta)" in source
        # The raw delta must no longer be handed to the client frame.
        assert 'message={"type": "assistant_text", "delta": delta}' not in source
