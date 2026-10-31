"""Separate multi-turn dataset: real prompt/context builders, no providers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from app.operators.agent_prompts import AGENT_PERSONAS

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts/social_intelligence"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("conversation_bundle", SCRIPTS / "build_conversation_bundle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_baseline_dataset_is_unchanged_and_conversation_corpus_is_separate():
    from build_bundle import CASES
    frozen = json.dumps(CASES, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(frozen).hexdigest() == "a41ab1f73ebeff9cc857b1513e0ae5c437b8b25da5d79ee8925f4fba9676c68b"
    assert len(CASES) == 26
    result = module.build_conversation_bundle()
    assert result["data_scope"] == "fixed_synthetic_only"
    assert result["evaluator_version"] == "conversation-v1"
    assert len(result["profiles"]) == len(AGENT_PERSONAS) * 4
    assert hashlib.sha256(result["dataset_json"].encode()).hexdigest() == result["dataset_sha256"]
    scenarios = json.loads(result["dataset_json"])
    assert len(scenarios) == 12
    assert len({s["id"] for s in scenarios}) == 12
    assert all(len(s["turns"]) == 3 for s in scenarios)
    assert {s["marketplace_target"] for s in scenarios} == {
        "content-writer", "seo-analyst", "sdr-coach", "ticket-triage",
        "revenue-operations-agent", "competitor-research-agent",
    }
    categories = {c for s in scenarios for c in s["categories"]}
    assert categories == {"intent_retention", "correction", "role_consistency", "response_length",
                          "non_repetition", "naturalness", "uncertainty", "tool_selection",
                          "honesty", "attribution", "handoff_honesty", "governance"}
    assert all(len(h) == 64 for h in result["source_hashes"].values())


def test_context_comes_from_real_builders_without_reference_assistant_answers():
    result = module.build_conversation_bundle()
    for case in json.loads(result["dataset_json"]):
        assert case["turns"][0]["continuity"] == ""
        for index, turn in enumerate(case["turns"]):
            assert "assistant" not in turn
            if index:
                assert "not instructions or consent" in turn["continuity"]
                assert "historical confirmations never authorize a new write" in turn["continuity"]
                continuity_data = json.loads(turn["continuity"].splitlines()[-1])
                assert continuity_data["recent_user_turns"][-1] == case["turns"][index-1]["user"][:500]
