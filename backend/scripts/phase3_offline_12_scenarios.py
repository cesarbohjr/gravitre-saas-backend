#!/usr/bin/env python3
"""Phase 3 offline contract evidence runner. No external providers or user data.

Each category re-executes actual repository tests against this checked-out SHA.
JUnit reports pytest-case execution duration, NOT customer turn latency or model
TTFT. Synthetic voice and mocked providers are never marked physical/live PASS.
"""
from __future__ import annotations
import json, os, subprocess, sys, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

CASES = [
 ("P3-01","intent",["tests/services/test_text_voice_task_execution_parity.py::test_google_ads_brief_reaches_reasoning_typed_and_spoken","tests/services/test_phase2_router_consumers.py::test_domain_strings_and_structured_domains_route_to_the_same_existing_engine"]),
 ("P3-02","contextual_memory",["tests/services/test_conversation_parity_benchmark.py::test_registry_is_valid_and_covers_required_lanes","tests/services/pipecat_voice/test_durable_conversation_parity.py"]),
 ("P3-03","sentiment",["tests/services/test_phase2_router_consumers.py::test_temporal_absence_and_disabled_sentiment_are_not_available_claims","tests/services/pipecat_voice/test_phase1_perception.py"]),
 ("P3-04","causal_reasoning",["tests/services/test_phase2_router_consumers.py::test_catalog_outputs_reach_semantic_consumers_and_keep_service_disclosures","tests/services/test_phase2_intelligence_coordination.py::test_optional_failures_are_visible_and_do_not_discard_other_capabilities"]),
 ("P3-05","temporal_relational",["tests/services/test_phase2_router_consumers.py::test_relational_resolution_reuses_scoped_known_nodes_without_extra_model_call","tests/services/test_phase2_router_consumers.py::test_unmatched_entity_stays_unknown_without_guessed_identifier"]),
 ("P3-06","predictive_adaptive",["tests/services/test_phase2_router_consumers.py::test_actual_loaded_model_output_reaches_router_through_existing_domain_engine","tests/services/test_phase2_intelligence_coordination.py::test_adaptive_opt_in_and_sample_gate_are_preserved_per_org"]),
 ("P3-07","response_quality_contract",["tests/services/test_conversation_parity_benchmark.py::test_parity_gate_compares_same_run_quality_instead_of_assumed_vendor_score","tests/services/test_phase2_router_consumers.py::test_actual_shared_turn_model_call_receives_all_seven_router_contributions"]),
 ("P3-08","text_latency_instrumentation",["tests/services/test_section_0_latency_envelope.py","tests/services/test_streamed_model_call_capture.py"]),
 ("P3-09","voice_synthetic_continuity",["tests/services/pipecat_voice/test_interruption_correctness.py","tests/services/pipecat_voice/test_voice_turn_trace_first_audio_kind.py","tests/services/pipecat_voice/test_confirmation_hold.py"]),
 ("P3-10","tool_execution",["tests/services/test_text_voice_task_execution_parity.py::test_multi_param_write_reaches_reasoning_typed_and_spoken","tests/services/test_approval_action_binding.py"]),
 ("P3-11","governance",["tests/services/test_org_approval_rules.py","tests/services/test_mcp_approval_binding.py","tests/services/test_agent_tool_permissions.py"]),
 ("P3-12","learning",["tests/services/test_intelligence_outcome_path.py::test_unknown_steps_do_not_invent_dollar_impact","tests/services/test_outcome_learning_handler.py","tests/services/test_outcome_ownership_learning_contamination.py"]),
]
def run():
    root=Path(__file__).resolve().parents[1]
    output=Path(os.environ.get("PHASE3_OUTPUT_DIR",str(root/"phase3-evidence")))
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for ident,dimension,selectors in CASES:
        junit=output/(ident+".xml")
        cmd=[sys.executable,"-m","pytest","-q","-p","tests.offline_network_guard","--disable-warnings","--maxfail=1","--junitxml",str(junit),*selectors]
        start=time.perf_counter()
        try:
            p=subprocess.run(cmd,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
            exit_code=p.returncode; log=p.stdout
        except subprocess.TimeoutExpired as exc:
            exit_code=124;log=(exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout,bytes) else (exc.stdout or "")
            log+="\nCASE TIMEOUT after 240s"
        (output/(ident+".log")).write_text(log[-40000:])
        summary={"tests":0,"failures":0,"errors":0,"skipped":0,"case_duration_seconds":[]}
        if junit.exists():
            tree=ET.parse(junit)
            for case in tree.iter("testcase"):
                summary["tests"]+=1
                summary["case_duration_seconds"].append(round(float(case.get("time","0")),5))
                for kind in ("failure","error","skipped"):
                    if case.find(kind) is not None: summary[kind+"s" if kind!="skipped" else kind]+=1
        # Execution duration measures the test harness, NOT the assistant response.
        status="PASS_OFFLINE_CONTRACT" if exit_code==0 and summary["tests"]>0 and summary["failures"]==0 and summary["errors"]==0 else "FAIL_OFFLINE_CONTRACT"
        entry={"id":ident,"dimension":dimension,"evidence_level":"offline_mock_or_synthetic_contract","status":status,"exit_code":exit_code,"pytest":summary,"wall_clock_test_seconds":round(time.perf_counter()-start,3),"first_useful_text_ms":None,"full_response_ms":None,"first_answer_audio_ms":None,"interruption_to_silence_ms":None,"physical_voice_verified":False,"live_tool_readback_verified":False,"selectors":selectors}
        results.append(entry)
        print(ident,status,summary["tests"],"tests",entry["wall_clock_test_seconds"],"s",flush=True)
    report={"schema":"gravitre.phase3.offline_eval.v1","timestamp_utc":datetime.now(timezone.utc).isoformat(),"github_sha":os.environ.get("GITHUB_SHA","unknown"),"source":"checked_out_repository","measurement_notice":"wall_clock_test_seconds and testcase durations measure pytest execution, NOT conversational turn or provider latency. No model/physical/provider SLA claim.","results":results,"total_cases":len(results),"passed_cases":sum(x["status"]=="PASS_OFFLINE_CONTRACT" for x in results),"failed_cases":sum(x["status"]=="FAIL_OFFLINE_CONTRACT" for x in results)}
    (output/"phase3-12-cases.json").write_text(json.dumps(report,indent=2)+"\n")
    return 0 if report["passed_cases"]==12 else 1
if __name__=="__main__":raise SystemExit(run())
