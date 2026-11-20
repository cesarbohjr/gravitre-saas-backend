"""Fail closed on missing QA lane and unsupported Voice 3.0/release success."""
import copy
import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[3]
validate = run_path(str(ROOT / "backend/scripts/master_qa_release_certifier.py"),
                    run_name="__qa90_test__")["validate"]


@pytest.fixture
def plan():
    return json.loads((ROOT / "docs/delivery/master-qa-00-90-release-manifest.json").read_text())


def test_release_manifest_is_honest_and_requires_voice_pr610(plan):
    report = validate(plan)
    assert report["lanes"] == 7
    assert report["certified"] == 0
    assert not report["release_authorized"]
    assert report["pr610_exact_head"]
    with pytest.raises(ValueError, match="full platform certification incomplete"):
        validate(plan, require_release=True)


def test_missing_qa_lane_cannot_pass(plan):
    plan["lanes"].pop(3)
    with pytest.raises(ValueError, match="lanes missing"):
        validate(plan)


def test_voice_qa30_cannot_pass_without_pr610_implementation(plan):
    plan["lanes"][3]["state"] = "CERTIFIED"
    with pytest.raises(ValueError, match="QA30 falsely certified"):
        validate(plan)


def test_claimed_release_cannot_hide_partial_lanes(plan):
    plan["release_authorized"] = True
    with pytest.raises(ValueError, match="release authorized while"):
        validate(plan)


def test_voice_acoustic_signoff_is_required(plan):
    plan["voice_dependency"]["certified"] = True
    with pytest.raises(ValueError, match="Voice 3.0 falsely certified"):
        validate(plan)
