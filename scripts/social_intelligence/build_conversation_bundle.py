"""Build a separate synthetic multi-turn corpus, preserving the 520-pair baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_bundle import ROOT, build_bundle


def build_conversation_bundle() -> dict:
    from app.services.dialogue_interpreter import interpret_dialogue
    from app.services.dialogue_session_continuity import build_session_continuity

    baseline = build_bundle()
    scenarios = json.loads(Path(__file__).with_name("conversation_cases.json").read_text())
    for scenario in scenarios:
        history = []
        for turn in scenario["turns"]:
            turn["dialogue"] = interpret_dialogue(turn["user"], contextual=True).prompt_section()
            turn["continuity"] = build_session_continuity(
                org_id="synthetic-org", user_id="synthetic-user", conversation_id=scenario["id"],
                history=history, task_state={},
            ).section
            history.append({"role": "user", "content": turn["user"]})
    dataset_json = json.dumps(scenarios, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    source_paths = [
        "scripts/social_intelligence/conversation_cases.json",
        "scripts/social_intelligence/build_bundle.py",
        "scripts/social_intelligence/build_conversation_bundle.py",
        "scripts/social_intelligence/evaluator.ts",
        "scripts/social_intelligence/conversation_evaluator.ts",
        "backend/app/services/dialogue_session_continuity.py",
    ]
    return {
        **{k: baseline[k] for k in ("source_sha", "source_dirty", "data_scope", "profiles")},
        "schema": 1, "evaluator_version": "conversation-v1",
        "source_hashes": {**baseline["source_hashes"], **{
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}},
        "dataset_json": dataset_json,
        "dataset_sha256": hashlib.sha256(dataset_json.encode()).hexdigest(),
        "baseline_cases_sha256": hashlib.sha256(json.dumps(
            baseline["cases"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest(),
        "scope": "synthetic generated-history conversations; no app ingress, tools, persistence, TTS or STT",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_conversation_bundle()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False) + "\n")
    print(json.dumps({"source_sha": result["source_sha"], "source_dirty": result["source_dirty"],
                      "dataset_sha256": result["dataset_sha256"], "profiles": len(result["profiles"])}))
