"""Quality gates for the curated multi-turn voice conversation examples."""
import json
from collections import Counter
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[1] / "app/services/pipecat_voice/conversation_multiturn_curated.json"

def test_curated_dialogue_coverage_and_distinctness():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert set(data["tiers"]) == {"light", "medium", "deep"}
    all_ids = set()
    for tier, examples in data["tiers"].items():
        assert len(examples) >= 16, tier
        assert len({example["scenario"] for example in examples}) == len(examples)
        assert len({example["trait"] for example in examples}) >= 5
        assistant_replies = []
        for example in examples:
            assert example["id"] not in all_ids
            all_ids.add(example["id"])
            assert [turn["role"] for turn in example["turns"]] == ["user", "assistant", "user", "assistant"]
            assert all(turn["text"].strip() for turn in example["turns"])
            assistant_replies.extend(turn["text"] for turn in example["turns"] if turn["role"] == "assistant")
        assert len(assistant_replies) == len(set(assistant_replies)), f"repeated assistant response in {tier}"

def test_dialogues_dont_claim_unverified_tool_operations():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    for examples in data["tiers"].values():
        for example in examples:
            for turn in example["turns"]:
                if turn["role"] == "assistant":
                    lower = turn["text"].lower()
                    assert "i already sent" not in lower
                    assert "i deployed it" not in lower
