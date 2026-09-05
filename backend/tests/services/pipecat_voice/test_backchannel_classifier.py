"""Mutation-proof tests for the backchannel-vs-interruption classifier.

Conversational-realism Phase 1. Each test asserts a real, closed-set
classification decision and includes a mutation-style negative assertion
(what would happen if the rule that decides it were reverted/removed) so a
future edit that quietly breaks the distinction fails loudly.
"""
from __future__ import annotations

from app.services.pipecat_voice.backchannel_classifier import (
    BackchannelClassification,
    classify_user_utterance,
    is_backchannel,
)


class TestBackchannelDetection:
    def test_single_word_affirmations_are_backchannel(self):
        for word in ["yeah", "yep", "yup", "yes", "okay", "ok", "sure", "right", "cool", "mhm"]:
            result = classify_user_utterance(word)
            assert result is BackchannelClassification.BACKCHANNEL, word
            assert is_backchannel(result)

    def test_uh_huh_variants_are_backchannel(self):
        for variant in ["uh-huh", "uh huh", "Uh-Huh", "UH HUH"]:
            assert classify_user_utterance(variant) is BackchannelClassification.BACKCHANNEL

    def test_short_multi_token_backchannel_phrases(self):
        for phrase in ["got it", "i see", "makes sense", "fair enough", "all right"]:
            assert classify_user_utterance(phrase) is BackchannelClassification.BACKCHANNEL

    def test_repeated_backchannel_tokens_still_backchannel(self):
        assert classify_user_utterance("yeah okay") is BackchannelClassification.BACKCHANNEL
        assert classify_user_utterance("right right") is BackchannelClassification.BACKCHANNEL

    def test_backchannel_with_trailing_punctuation(self):
        assert classify_user_utterance("Yeah!") is BackchannelClassification.BACKCHANNEL
        assert classify_user_utterance("Okay,") is BackchannelClassification.BACKCHANNEL

    def test_backchannel_word_followed_by_real_content_is_not_backchannel(self):
        """MUTATION PROOF: dropping the max-words/full-match guard would let
        "yeah but I actually need it sent to someone else" be swallowed as a
        backchannel - the exact live bug this phase exists to prevent.
        """
        result = classify_user_utterance("yeah but I actually need it sent to someone else")
        assert result is not BackchannelClassification.BACKCHANNEL
        assert not is_backchannel(result)

    def test_yeah_but_short_is_not_backchannel(self):
        # "yeah but" - two tokens, but "but" is not in the closed vocabulary.
        result = classify_user_utterance("yeah but")
        assert result is not BackchannelClassification.BACKCHANNEL


class TestStopCommand:
    def test_stop_words_classify_as_stop_command(self):
        for phrase in ["stop", "wait", "hold on", "hang on", "pause", "cancel that", "never mind"]:
            assert classify_user_utterance(phrase) is BackchannelClassification.STOP_COMMAND

    def test_stop_command_is_not_backchannel(self):
        """MUTATION PROOF: a stop command must never be treated as an
        affirmation that lets the agent keep talking over the user.
        """
        result = classify_user_utterance("stop")
        assert not is_backchannel(result)
        assert result is BackchannelClassification.STOP_COMMAND


class TestCorrection:
    def test_correction_prefixes_detected(self):
        assert classify_user_utterance("no, that's not what I said") is BackchannelClassification.CORRECTION
        assert classify_user_utterance("actually I need it by Friday") is BackchannelClassification.CORRECTION
        assert classify_user_utterance("I meant the other deal") is BackchannelClassification.CORRECTION

    def test_correction_is_not_backchannel(self):
        result = classify_user_utterance("no that's wrong")
        assert not is_backchannel(result)


class TestNewQuestion:
    def test_question_words_detected(self):
        assert classify_user_utterance("what about the other one") is BackchannelClassification.NEW_QUESTION
        assert classify_user_utterance("can you check Slack too") is BackchannelClassification.NEW_QUESTION

    def test_question_mark_detected(self):
        assert classify_user_utterance("is that the right one?") is BackchannelClassification.NEW_QUESTION

    def test_question_is_not_backchannel(self):
        result = classify_user_utterance("how long will that take")
        assert not is_backchannel(result)


class TestInterruptionFallback:
    def test_generic_new_content_defaults_to_interruption(self):
        result = classify_user_utterance("send it to Sarah instead of Mike")
        assert result is BackchannelClassification.INTERRUPTION

    def test_empty_text_defaults_to_interruption_not_backchannel(self):
        """MUTATION PROOF: an empty/unknown transcript must never be treated
        as a free pass to keep talking over the user - ambiguous input must
        resolve to the safe (interrupt) side, never the unsafe (suppress) side.
        """
        assert classify_user_utterance("") is BackchannelClassification.INTERRUPTION
        assert classify_user_utterance("   ") is BackchannelClassification.INTERRUPTION
        assert not is_backchannel(classify_user_utterance(""))

    def test_gibberish_defaults_to_interruption(self):
        result = classify_user_utterance("the quarterly numbers look off to me")
        assert result is BackchannelClassification.INTERRUPTION
        assert not is_backchannel(result)
