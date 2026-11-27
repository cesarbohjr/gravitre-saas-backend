"""Consolidate same-run candidate evidence; never authorize runtime activation."""
import argparse
import json
import os
from pathlib import Path
from voice3_acoustic_eval import certification_blockers
from voice3_pipecat_probe import candidate_ids, evaluate_status, MODEL, FLASH, FIXTURE_VERSION, TRIALS

def consolidate(proposal, probe, sha):
    ids = candidate_ids(proposal,sha)
    if (probe.get("source_sha") != sha or probe.get("activation_authorized") is not False
            or probe.get("fixture_version") != FIXTURE_VERSION or probe.get("model") != MODEL):
        raise ValueError("probe identity mismatch")
    rows = probe["rows"]
    if len(rows) != len(ids) or {r["voice_id"] for r in rows} != set(ids):
        raise ValueError("incomplete or duplicate probe coverage")
    index = {r["voice_id"]:r for r in rows}
    out = []
    for row in proposal["mapping"]:
        voice = row.get("candidate_id")
        gates = dict(row.get("provider_quality",{}).get("gates",{}))
        # Only the known provider HTTP gate results can be imported from the
        # proposal; all other gates require their own authenticated evidence.
        gates = {k:gates[k] for k in ("flash_http","v3_dialogue","acoustic_integrity","intelligibility") if k in gates}
        pair = index.get(voice,{})
        if pair:
            valid = all(isinstance(pair.get(label),list) and len(pair[label]) == TRIALS
                        and all(t.get("trial") == i and t.get("voice_id") == voice
                                and t.get("model") == model and t.get("fixture_version") == FIXTURE_VERSION
                                and t.get("status") == "PASS" and evaluate_status(t) == "PASS"
                                for i,t in enumerate(pair[label]))
                        for label,model in (("flash_trials",FLASH),("dialogue_trials",MODEL)))
            # Adapter-local cancellation is useful evidence but remote provider
            # termination is not established. Never upgrade it to certification.
            gates["interruption"] = "NOT RUN" if valid else "FAIL"
            gates["live_streaming"] = "NOT RUN" if valid else "FAIL"
        blockers = certification_blockers(gates)
        out.append({"preset":row["preset"],"candidate_id":voice,"gates":gates,
                    "blockers":blockers,"adapter_probe_status":pair.get("status","NOT RUN")})
    return {"source_sha":sha,"activation_authorized":False,"status":"BLOCKED" if any(r["blockers"] for r in out) else "REVIEW_REQUIRED",
            "rows":out,"certifiable_ids":[r["candidate_id"] for r in out if r["candidate_id"] and not r["blockers"]]}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("proposal","probe","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    try:
        result=consolidate(json.loads(args.proposal.read_text()),json.loads(args.probe.read_text()),os.getenv("GITHUB_SHA",""))
    except Exception as exc:
        result={"source_sha":os.getenv("GITHUB_SHA",""),"status":"FAIL","activation_authorized":False,"certifiable_ids":[],"error_type":type(exc).__name__}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(result["status"])
    return 1 if result["status"]=="FAIL" else 0

if __name__=="__main__":
    raise SystemExit(main())
