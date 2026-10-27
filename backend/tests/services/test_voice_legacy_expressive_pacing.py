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


def test_expressive_phrase_tiers_are_bounded():
    from app.services.voice_session_service import expression_tier_for_phrase
    assert expression_tier_for_phrase("Really?") == "light"
    assert expression_tier_for_phrase("That's great!") == "light"
    assert expression_tier_for_phrase("Here is the answer.") == "medium"
    assert expression_tier_for_phrase("Here is the explanation:") == "deep"


def test_provider_expression_preserves_conversational_style_and_similarity():
    from app.services.tier1_voice_service import expressive_voice_settings
    assert expressive_voice_settings("light")["stability"] == 0.4
    assert expressive_voice_settings("medium")["stability"] == 0.5
    assert expressive_voice_settings("deep")["stability"] == 0.6
    for tier in ("light", "medium", "deep", "unknown"):
        settings = expressive_voice_settings(tier)
        assert settings["style"] == 0.0
        assert settings["similarity_boost"] == 0.75
        assert settings["use_speaker_boost"] is True
