"""Quality gates for the curated voice dialogue library.

Synthetic, offline checks: schema, uniqueness, opener diversity, trait and
tier-transition coverage, the deterministic rubric on every reference reply,
and the runtime few-shot selector's size, determinism, speed and safety.
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from itertools import permutations

import pytest

from app.services.pipecat_voice import dialogue_library
from app.services.pipecat_voice.dialogue_library import (
    EVAL_CONVERSATIONS_PATH,
    HEADER,
    RUNTIME_FEWSHOTS_PATH,
    select_fewshots,
)
from app.services.pipecat_voice.dialogue_library import rubric

TIERS = rubric.TIERS
EVAL = json.loads(EVAL_CONVERSATIONS_PATH.read_text(encoding="utf-8"))
RUNTIME = json.loads(RUNTIME_FEWSHOTS_PATH.read_text(encoding="utf-8"))
CONVS = EVAL["conversations"]
VOCAB = set(EVAL["trait_vocabulary"])


def _assistant_turns():
    for conv in CONVS:
        for turn in conv["turns"]:
            if turn["role"] == "assistant":
                yield conv, turn


def _dialogue_len(conv) -> int:
    return sum(1 for t in conv["turns"] if t["role"] != "tool")


# --- eval set: schema -------------------------------------------------------

def test_eval_set_is_labelled_as_evaluation_not_training():
    assert "not training" in EVAL["purpose"].lower()
    assert "not training" in RUNTIME["purpose"].lower()


def test_eval_schema():
    assert len(CONVS) >= 150
    ids = [c["id"] for c in CONVS]
    assert len(ids) == len(set(ids))
    for conv in CONVS:
        assert set(conv) <= {"id", "tier_path", "traits", "turns", "source"}, conv["id"]
        assert conv["traits"] and set(conv["traits"]) <= VOCAB, conv["id"]
        assert conv["turns"][0]["role"] == "user", conv["id"]
        assert conv["turns"][-1]["role"] == "assistant", conv["id"]
        assert 3 <= _dialogue_len(conv) <= 8, conv["id"]
        path = []
        previous_role = None
        for turn in conv["turns"]:
            assert turn["role"] in {"user", "assistant", "tool"}, conv["id"]
            assert isinstance(turn["text"], str) and turn["text"].strip(), conv["id"]
            assert not (turn["role"] == "user" and previous_role == "user"), conv["id"]
            previous_role = turn["role"]
            if turn["role"] == "assistant":
                assert turn["tier"] in TIERS, conv["id"]
                if not path or path[-1] != turn["tier"]:
                    path.append(turn["tier"])
                expect = turn.get("expect", {})
                assert set(expect) <= {"must", "must_not"}, conv["id"]
                assert all(isinstance(x, str) and x for v in expect.values() for x in v), conv["id"]
            elif turn["role"] == "tool":
                assert re.fullmatch(r"[a-z_]+\.[a-z_]+", turn["tool"]), conv["id"]
            else:
                assert set(turn) == {"role", "text"}, conv["id"]
        assert conv["tier_path"] == path, conv["id"]


def test_eval_lengths_are_varied():
    lengths = Counter(_dialogue_len(c) for c in CONVS)
    assert len(lengths) >= 4
    assert lengths.most_common(1)[0][1] / len(CONVS) <= 0.7


def test_tool_turns_use_fictional_email_domains():
    for conv in CONVS:
        for turn in conv["turns"]:
            for address in re.findall(r"[\w.+-]+@[\w.-]+", turn["text"]):
                assert address.endswith(".example"), (conv["id"], address)


# --- eval set: uniqueness and diversity ---------------------------------------

def test_no_duplicate_assistant_texts():
    texts = [t["text"] for _, t in _assistant_turns()]
    dupes = [t for t, n in Counter(texts).items() if n > 1]
    assert not dupes


def test_opener_diversity():
    openers = Counter(rubric.opener(t["text"]) for _, t in _assistant_turns())
    total = sum(openers.values())
    worst, count = openers.most_common(1)[0]
    assert count / total <= 0.03, (worst, count, total)


# --- eval set: coverage ---------------------------------------------------------

def test_every_trait_is_covered():
    counts = Counter(t for c in CONVS for t in c["traits"])
    missing = {t for t in VOCAB if counts[t] < 2}
    assert not missing


def test_every_tier_transition_pair_is_covered():
    pairs = Counter()
    for conv in CONVS:
        pairs.update(zip(conv["tier_path"], conv["tier_path"][1:]))
    for pair in permutations(TIERS, 2):
        assert pairs[pair] >= 3, pair
    single = Counter(c["tier_path"][0] for c in CONVS if len(c["tier_path"]) == 1)
    assert all(single[t] >= 20 for t in TIERS), single
    assert sum(1 for c in CONVS if len(c["tier_path"]) >= 3) >= 5


def test_deep_conversations_use_tools_or_placeholders():
    for conv in CONVS:
        if "business_read" in conv["traits"]:
            has_tool = any(t["role"] == "tool" for t in conv["turns"])
            has_slot = any(re.search(r"<[a-z]", t["text"]) for t in conv["turns"] if t["role"] == "assistant")
            assert has_tool or has_slot, conv["id"]


# --- eval set: rubric ------------------------------------------------------------

@pytest.mark.parametrize("conv", CONVS, ids=[c["id"] for c in CONVS])
def test_reference_conversation_passes_rubric(conv):
    history: list[dict] = []
    for turn in conv["turns"]:
        if turn["role"] == "assistant":
            violations = rubric.check_reply(
                turn["text"], turn["tier"], history, allow_placeholders=True, require_tool_evidence=True
            )
            assert not violations, (turn["text"], violations)
        history.append(turn)
    assert not rubric.check_conversation(conv["turns"])


# --- rubric: it actually catches the defects it claims to -------------------

def _codes(violations):
    return {v.code for v in violations}


@pytest.mark.parametrize(
    "reply,code",
    [
        ("**Pipeline**: three deals.", "markdown"),
        ("- first item", "markdown"),
        ("See https://example.com for more.", "url"),
        ("Record 3f2a9c1e-1b2c-4d5e-8f90-1234567890ab is updated.", "identifier"),
        ("Great question! It depends.", "sycophancy"),
        ("You're so clueless about this.", "insult"),
        ("Want tacos? Or pizza?", "stacked_questions"),
        ("Line one.\nLine two.", "multiline"),
        ("As an AI, I can't say.", "filler"),
    ],
)
def test_rubric_flags_style_defects(reply, code):
    assert code in _codes(rubric.check_reply(reply, "medium"))


def test_rubric_length_budget():
    long_reply = "word " * (rubric.WORD_BUDGET["light"] + 1)
    assert "too_long_words" in _codes(rubric.check_length(long_reply, "light"))
    assert not rubric.check_length(long_reply, "deep")


def test_rubric_flags_unsolicited_business_in_light():
    history = [{"role": "user", "text": "Hey, good morning!"}]
    reply = "Morning! By the way, your pipeline has a few open deals."
    assert "unsolicited_business" in _codes(rubric.check_reply(reply, "light", history))
    asked = [{"role": "user", "text": "How's my pipeline?"}]
    assert "unsolicited_business" not in _codes(rubric.check_reply(reply, "light", asked))


def test_rubric_write_claims_need_approval_and_evidence():
    ask = [{"role": "user", "text": "Post the update in sales."}]
    assert "write_without_approval" in _codes(rubric.check_reply("Posted in sales.", "deep", ask))
    assert "write_without_approval" in _codes(rubric.check_reply("I've sent it to Dana.", "deep", ask))
    approved = ask + [
        {"role": "assistant", "text": "I'd post: we're live. Post it?"},
        {"role": "user", "text": "Yes."},
    ]
    assert not rubric.check_reply("Posted in sales.", "deep", approved)
    assert "write_without_tool_evidence" in _codes(
        rubric.check_reply("Posted in sales.", "deep", approved, require_tool_evidence=True)
    )
    executed = approved + [{"role": "tool", "text": "ok=true"}]
    assert not rubric.check_reply("Posted in sales.", "deep", executed, require_tool_evidence=True)
    assert not rubric.check_reply("Nothing's been sent yet.", "deep", ask)
    assert not rubric.check_reply("I won't post anything.", "deep", ask)


def test_rubric_flags_invented_numbers_in_deep():
    history = [{"role": "user", "text": "How many leads?"}, {"role": "tool", "text": "count 17"}]
    assert not rubric.check_reply("You have 17 new leads.", "deep", history)
    assert "ungrounded_number" in _codes(rubric.check_reply("You have 57 new leads.", "deep", history))


def test_rubric_conversation_checks():
    nagging = [
        {"role": "user", "text": "Hi"},
        {"role": "assistant", "text": "Hi there. How are you?"},
        {"role": "user", "text": "Fine"},
        {"role": "assistant", "text": "Glad to hear. What's new?"},
        {"role": "user", "text": "Nothing"},
        {"role": "assistant", "text": "Fair enough. Anything planned?"},
    ]
    assert "follow_up_rate" in _codes(rubric.check_conversation(nagging))
    repetitive = [
        {"role": "user", "text": "a"},
        {"role": "assistant", "text": "I hear you. Go on."},
        {"role": "user", "text": "b"},
        {"role": "assistant", "text": "I hear you. That's rough."},
    ]
    codes = _codes(rubric.check_conversation(repetitive))
    assert {"repeated_opener", "repeated_opener_consecutive"} <= codes


# --- runtime few-shots -----------------------------------------------------------

RUNTIME_EXAMPLES = [(tier, ex) for tier, exs in RUNTIME["tiers"].items() for ex in exs]


def test_runtime_fewshot_counts():
    counts = {tier: len(RUNTIME["tiers"].get(tier, [])) for tier in TIERS}
    # Large enough to cover the situations people actually raise; selection
    # stays lexical and under 1 ms (test_select_fewshots_is_fast).
    assert counts["light"] >= 40
    assert counts["medium"] >= 40
    assert counts["deep"] >= 35
    ids = [ex["id"] for _, ex in RUNTIME_EXAMPLES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("tier,example", RUNTIME_EXAMPLES, ids=[ex["id"] for _, ex in RUNTIME_EXAMPLES])
def test_runtime_fewshot_quality(tier, example):
    turns = example["turns"]
    assert 2 <= len(turns) <= 4
    assert [t["role"] for t in turns] == ["user", "assistant"] * (len(turns) // 2)
    assert sum(len(t["text"]) for t in turns) < 300
    assert set(example["traits"]) <= VOCAB
    history: list[dict] = []
    for turn in turns:
        if turn["role"] == "assistant":
            assert not rubric.check_reply(turn["text"], tier, history), turn["text"]
            if tier == "deep":
                assert not re.search(r"\d", turn["text"]), "deep examples must not carry numbers"
        history.append(turn)
    assert not rubric.check_conversation(turns)


def test_runtime_assistant_texts_unique():
    texts = [t["text"] for _, ex in RUNTIME_EXAMPLES for t in ex["turns"] if t["role"] == "assistant"]
    assert len(texts) == len(set(texts))


# --- select_fewshots ---------------------------------------------------------------

PROBES = [
    ("light", "Tell me a joke"),
    ("light", "Oh great, another Monday"),
    ("light", "I got laid off today"),
    ("light", "um, actually scratch that"),
    ("light", ""),
    ("medium", "Why do cats purr?"),
    ("medium", "Should I use text or email for reminders?"),
    ("medium", "Give me name ideas for my shop"),
    ("deep", "Send Dana the follow-up email"),
    ("deep", "Pause the brand campaign"),
    ("deep", "Why did conversions drop last week?"),
] + [(tier, t["text"]) for tier, ex in RUNTIME_EXAMPLES for t in ex["turns"] if t["role"] == "user"]


def _example_count(block: str) -> int:
    return block.count("\n\nUser:")


@pytest.mark.parametrize("tier,message", PROBES)
def test_select_fewshots_size_and_shape(tier, message):
    block = select_fewshots(tier, message, k=3)
    assert block.startswith(HEADER)
    assert len(block) <= dialogue_library.MAX_BLOCK_CHARS
    assert 1 <= _example_count(block) <= (1 if tier == "deep" else 3)
    assert select_fewshots(tier, message, k=3) == block


def test_select_fewshots_deep_returns_at_most_one():
    assert _example_count(select_fewshots("deep", "send the email and pause the campaign", k=5)) == 1


def test_select_fewshots_matches_obvious_cases():
    assert "Its days were numbered" in select_fewshots("light", "tell me a funny joke", k=1)
    assert "gut punch" in select_fewshots("light", "I just got laid off", k=1)
    assert "Should I send that?" in select_fewshots("deep", "email Dana for me", k=1)
    approval = select_fewshots(
        "deep", "yes", history=[{"role": "assistant", "text": "Want me to send it?"}], k=1
    )
    assert "Should I send that?" in approval or "Should I pause it?" in approval


def test_select_fewshots_skips_examples_already_in_history():
    first = select_fewshots("light", "tell me a joke", k=1)
    history = [{"role": "assistant", "text": "Why did the calendar look nervous? Its days were numbered."},
               {"role": "assistant", "text": "You did ask for terrible."}]
    second = select_fewshots("light", "tell me a joke", history=history, k=1)
    assert second and second != first
    assert "Its days were numbered" not in second


@pytest.mark.parametrize(
    "tier,message,history,k",
    [
        ("nope", "hello", None, 2),
        ("light", "hello", None, 0),
        ("light", None, None, 2),
        ("light", "hello", ["not a dict", 3], 2),
        (None, "hello", None, 2),
    ],
)
def test_select_fewshots_never_raises(tier, message, history, k):
    out = select_fewshots(tier, message, history, k)  # type: ignore[arg-type]
    assert isinstance(out, str)
    if tier not in TIERS or k < 1:
        assert out == ""


def test_select_fewshots_returns_empty_on_load_failure(monkeypatch):
    def boom():
        raise OSError("missing")

    monkeypatch.setattr(dialogue_library, "_load_runtime", boom)
    assert select_fewshots("light", "hello") == ""


def test_select_fewshots_is_fast():
    select_fewshots("medium", "warm up")
    message = "Why is the sky blue, and should I learn guitar or piano this year?"
    history = [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "Hey there."}] * 5
    runs = 500
    start = time.perf_counter()
    for _ in range(runs):
        select_fewshots("medium", message, history)
    per_call = (time.perf_counter() - start) / runs
    assert per_call < 0.001, per_call
