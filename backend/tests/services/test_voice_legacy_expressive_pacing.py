"""Legacy HTTP duplex TTS phrase pacing regressions."""
from app.services.voice_session_service import split_speakable_chunks


def test_short_clause_is_held_until_sentence_finishes():
    text = "I think this is a good idea, but"
    assert split_speakable_chunks(text) == ([], text)


def test_long_semicolon_clause_splits_at_breath_point():
    prefix = "Here is a practical explanation with enough detail to keep the speaking rhythm natural and clear"
    text = prefix + "; the next thought continues without an abrupt ending"
    chunks, remaining = split_speakable_chunks(text)
    assert chunks == [prefix + ";"]
    assert remaining == "the next thought continues without an abrupt ending"


def test_long_comma_clause_preserves_punctuation():
    prefix = "The answer needs a little context because there are several important considerations that change the outcome depending on the situation"
    text = prefix + ", and the next thought continues with more information"
    chunks, remaining = split_speakable_chunks(text)
    assert chunks == [prefix + ","]
    assert remaining == "and the next thought continues with more information"


def test_complete_short_sentence_is_not_rewritten():
    text = "That sounds good."
    chunks, remaining = split_speakable_chunks(text)
    assert chunks == [text]
    assert remaining == ""
