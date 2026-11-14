"""QA00–90 release manifest contract; no CI pass can stand in for live proof."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILE = ROOT / "docs/delivery/master-qa-00-90-release-manifest.json"
EXPECTED = ("QA00", "QA10", "QA20", "QA30", "QA40", "QA50", "QA90")
STATES = {"BLOCKED", "PARTIAL", "CERTIFIED"}
SHA = re.compile(r"^[0-9a-f]{40}$")


def validate(manifest: dict, *, require_release: bool = False) -> dict:
    lanes = manifest.get("lanes", [])
    ids = [x.get("id") for x in lanes]
    errors = []
    if tuple(ids) != EXPECTED:
        errors.append("QA00–90 lanes missing, duplicated or out of release order")
    for lane in lanes:
        if lane.get("state") not in STATES:
            errors.append(f"{lane.get('id')} missing explicit release state")
        if not lane.get("domain") or not lane.get("evidence") or not lane.get("remaining"):
            errors.append(f"{lane.get('id')} missing scope/evidence/gaps")
        if lane.get("state") == "CERTIFIED":
            proof = lane.get("certification", {})
            if not SHA.fullmatch(str(proof.get("executed_sha", ""))):
                errors.append(f"{lane.get('id')} certified without exact SHA")
            if not proof.get("ci_run_url") or not proof.get("owner_approved"):
                errors.append(f"{lane.get('id')} certified without CI and owner approval")
            if not proof.get("negative_tests") or not proof.get("downstream_evidence"):
                errors.append(f"{lane.get('id')} certified without negative and downstream verification")
            if lane.get("id") in {"QA40", "QA50", "QA90"} and (
                not proof.get("production_deployed_sha") or not proof.get("rollback_verified")
            ):
                errors.append(f"{lane.get('id')} certified without deployed SHA and rollback")
    voice = manifest.get("voice_dependency", {})
    if voice.get("owner_pr") != 610 or not SHA.fullmatch(str(voice.get("head", ""))):
        errors.append("Voice 3.0 must bind exact PR610 head")
    if set(voice.get("required_milestones", [])) != {f"V{i}" for i in range(8)}:
        errors.append("PR610 Voice V0–V7 milestone coverage incomplete")
    if voice.get("certified"):
        if (voice.get("implementation_evidence") == "NOT_PROVIDED"
            or voice.get("human_acoustic_acceptance") != "PASS"):
            errors.append("Voice 3.0 falsely certified without implementation/acoustics")
    if any(l.get("id") == "QA30" and l.get("state") == "CERTIFIED" for l in lanes) and not voice.get("certified"):
        errors.append("QA30 falsely certified without PR610")
    all_certified = len(lanes) == len(EXPECTED) and all(x.get("state") == "CERTIFIED" for x in lanes)
    if manifest.get("release_authorized") and (not all_certified or not voice.get("certified")):
        errors.append("release authorized while required lanes or voice remain incomplete")
    if require_release and (not manifest.get("release_authorized") or not all_certified):
        errors.append("full platform certification incomplete; fail closed")
    if errors:
        raise ValueError("; ".join(errors))
    return {"lanes":len(lanes),"certified":sum(x.get("state")=="CERTIFIED" for x in lanes),
            "blocked":sum(x.get("state")=="BLOCKED" for x in lanes),
            "release_authorized":bool(manifest.get("release_authorized")),
            "pr610_exact_head":voice.get("head"), "source_only":True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-release",action="store_true")
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    report = validate(json.loads(FILE.read_text()),require_release=args.require_release)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
