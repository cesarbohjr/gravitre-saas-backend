#!/usr/bin/env python3
"""Read-only account discovery and bounded candidate synthesis. Never activates voices."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
MAX_PAGES = 10
MAX_CANDIDATES = 12

def norm(value):
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

def eligible(raw):
    vid = raw.get("voice_id", "")
    labels = raw.get("labels") or {}
    sharing = raw.get("sharing") or {}
    # Unknown pricing is not evidence of standard pricing. Only explicitly
    # standard rates or account premade voices with no rate qualify.
    rate = sharing.get("rate")
    standard = (rate == 1 or rate == "1" or rate == "1.0"
                or (rate is None and raw.get("category") == "premade"))
    return (isinstance(vid, str) and re.fullmatch(r"[A-Za-z0-9]{16,64}", vid)
            and isinstance(labels, dict) and standard)

def match(curated, voices):
    """Conservative unique assignments; never guess gender or accent."""
    reserved = set(curated)
    used = set()
    rows = []
    for old_id, meta in curated.items():
        ranked = []
        for raw in voices:
            vid = raw.get("voice_id")
            if vid in used or (vid in reserved and vid != old_id) or not eligible(raw):
                continue
            labels = raw.get("labels") or {}
            if norm(labels.get("gender")) != norm(meta["gender"]):
                continue
            if norm(labels.get("accent")) != norm(meta["accent_region"]):
                continue
            # Existing ID gets priority if metadata agrees, avoiding gratuitous
            # voice changes. Other candidates are proposals, not identity proof.
            score = 100 if vid == old_id else 0
            score += 5 * (norm(labels.get("age")) == norm(meta["age_range"]))
            words = set(re.findall(r"[a-z]+", str(labels.get("description", "")).lower()
                                    + " " + str(labels.get("descriptive", "")).lower()))
            score += len(words & set(re.findall(r"[a-z]+", meta["descriptor"].lower())))
            ranked.append((-score, vid))
        ranked.sort()
        chosen = ranked[0][1] if ranked else None
        if chosen:
            used.add(chosen)
        rows.append({"preset": meta["key"], "legacy_id": old_id,
                     "candidate_id": chosen, "gender": meta["gender"],
                     "accent": meta["accent_region"], "descriptor": meta["descriptor"],
                     "categories": meta["categories"], "match_score": -ranked[0][0] if ranked else None,
                     "decision": "REVIEW_REQUIRED" if chosen else "UNMATCHED"})
    return rows

def discover(client, key):
    # Account-accessible voices only; no provider-side additions or purchases.
    voices = {}
    token = None
    seen = set()
    for _ in range(MAX_PAGES):
        params = {"page_size": 100}
        if token:
            params["next_page_token"] = token
        response = client.get("https://api.elevenlabs.io/v2/voices",
                              headers={"xi-api-key": key}, params=params)
        response.raise_for_status()
        data = response.json()
        for raw in data["voices"]:
            if isinstance(raw, dict) and isinstance(raw.get("voice_id"), str):
                voices[raw["voice_id"]] = raw
        if data.get("has_more") is False:
            return list(voices.values())
        token = data.get("next_page_token")
        if not isinstance(token, str) or not token or token in seen:
            raise ValueError("Incomplete discovery")
        seen.add(token)
    raise ValueError("Discovery page bound exceeded")

def propose(env, transport=None, probe_fn=None):
    import httpx
    from app.services.voice_library_service import CURATED_VOICE_META
    result = {"status": "NOT RUN", "source_sha": env.get("GITHUB_SHA", ""),
              "activation_authorized": False, "physical_acceptance": "NOT RUN",
              "scope": "Account inventory, metadata matching and HTTP Flash synthesis only",
              "mapping": [], "compatibility": []}
    key = env.get("ELEVENLABS_API_KEY")
    if not key:
        return result
    try:
        with httpx.Client(timeout=15, follow_redirects=False, transport=transport) as client:
            voices = discover(client, key)
        result["discovered_count"] = len(voices)
        rows = match(CURATED_VOICE_META, voices)
        result["mapping"] = rows
        ids = [r["candidate_id"] for r in rows if r["candidate_id"]]
        if ids:
            if len(ids) > MAX_CANDIDATES:
                raise ValueError("Candidate bound exceeded")
            if probe_fn is None:
                spec = importlib.util.spec_from_file_location("catalog_probe", ROOT / "scripts/verify-voice-catalog.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                probe_fn = module.probe
            evidence = probe_fn({**env, "VOICE_3_APPROVED_VOICE_IDS": ",".join(ids)}, transport=transport)
            result["compatibility"] = evidence.get("rows", [])
        passed = {r["voice_id"] for r in result["compatibility"] if r.get("passed") is True}
        for row in rows:
            row["flash_http_passed"] = row["candidate_id"] in passed
        result["status"] = ("READY_FOR_REVIEW" if len(rows) == len(CURATED_VOICE_META)
                            and all(r["flash_http_passed"] for r in rows)
                            else "INCOMPLETE")
        result["proposed_ids"] = [r["candidate_id"] for r in rows if r["flash_http_passed"]]
    except Exception as exc:
        result["status"] = "FAIL"
        result["error_type"] = type(exc).__name__
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = propose(os.environ)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"])
    return 0 if result["status"] == "READY_FOR_REVIEW" else 1

if __name__ == "__main__":
    raise SystemExit(main())
