import importlib.util
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("proposal", ROOT / "scripts/propose-voice3-catalog.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

OLD = "A" * 20
NEW = "B" * 20
META = {"key": "test", "gender": "female", "accent_region": "american",
        "age_range": "adult", "descriptor": "Warm professional", "categories": ["general"]}

def voice(vid=NEW, gender="female", accent="american", rate=1):
    return {"voice_id": vid, "labels": {"gender": gender, "accent": accent, "age": "adult"},
            "sharing": {"rate": rate}, "category": "professional"}

def test_match_preserves_current_id_when_eligible():
    assert mod.match({OLD: META}, [voice(), voice(OLD)])[0]["candidate_id"] == OLD

@pytest.mark.parametrize("raw", [voice(gender="male"), voice(accent="british"), voice(rate=2), voice(rate=None)])
def test_no_incompatible_or_unknown_rate_candidate(raw):
    assert mod.match({OLD: META}, [raw])[0]["candidate_id"] is None

def test_unique_assignments_and_no_approval():
    rows = mod.match({OLD: META, "C"*20: {**META, "key": "other"}}, [voice()])
    assert [r["candidate_id"] for r in rows] == [NEW, None]
    assert rows[0]["decision"] == "REVIEW_REQUIRED"

def test_discovery_paginates_without_mutations():
    def handler(req):
        assert req.method == "GET"
        if req.url.params.get("next_page_token"):
            return httpx.Response(200, json={"voices": [voice(OLD)], "has_more": False})
        return httpx.Response(200, json={"voices": [voice()], "has_more": True, "next_page_token": "next"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert len(mod.discover(client, "test")) == 2

def test_incomplete_discovery_fails():
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"voices": [], "has_more": True}))) as client:
        with pytest.raises(ValueError):
            mod.discover(client, "test")

def test_missing_credentials_never_approves():
    result = mod.propose({})
    assert result["status"] == "NOT RUN"
    assert result["activation_authorized"] is False
