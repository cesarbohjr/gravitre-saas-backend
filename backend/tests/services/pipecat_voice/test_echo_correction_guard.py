"""Barge-in corrections must survive echo suppression without false matches."""
from app.services.pipecat_voice.voice_audio_origin import is_echo_of

def test_contiguous_assistant_echo_is_suppressed():
    assert is_echo_of("check your website traffic", ["check your website traffic in analytics"])

def test_cross_segment_or_reordered_words_are_not_echoes():
    spoken = ["check your website traffic", "show your website visitors"]
    assert not is_echo_of("check your website visitors", spoken)

def test_explicit_correction_with_repeated_words_is_not_echo():
    spoken = ["check your website traffic in google analytics"]
    assert not is_echo_of("actually check your website traffic", spoken)
    assert not is_echo_of("stop check your website traffic", spoken)

def test_unrelated_speech_is_not_echo():
    assert not is_echo_of("show me the invoices from last week", ["check your website traffic"])
