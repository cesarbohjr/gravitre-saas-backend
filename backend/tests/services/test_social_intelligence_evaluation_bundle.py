"""The model evaluation corpus is separate from runtime training and uses all roles."""
import importlib.util
from pathlib import Path

from app.operators.agent_prompts import AGENT_PERSONAS

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("social_bundle", ROOT / "scripts/social_intelligence/build_bundle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_bundle_uses_real_prompt_builders_for_every_role_channel_and_path():
    bundle = module.build_bundle()
    assert len(bundle["profiles"]) == len(AGENT_PERSONAS) * 4
    assert {p["role"] for p in bundle["profiles"]} == set(AGENT_PERSONAS)
    assert {p["path"] for p in bundle["profiles"]} == {"unified", "classical"}
    assert {p["channel"] for p in bundle["profiles"]} == {"text", "voice"}
    for profile in bundle["profiles"]:
        assert "Emotional and social awareness" in profile["system"]
        assert "approval" in profile["system"]
        if profile["channel"] == "voice":
            assert "SPOKEN" in profile["system"]
    assert bundle["data_scope"] == "fixed_synthetic_only"
    assert all(case["messages"][-1]["role"] == "user" for case in bundle["cases"])
    assert len({c["id"] for c in bundle["cases"]}) == 16
    assert len(bundle["source_sha"]) == 40
    assert all(len(h) == 64 for h in bundle["source_hashes"].values())
    assert {"negated_emotion", "negated_positive", "targeted_abuse", "quoted_abuse", "pressure_consent", "no_emotional_profile", "emotion_repair"} <= {c["id"] for c in bundle["cases"]}
