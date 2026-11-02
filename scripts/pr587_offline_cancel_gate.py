"""No-provider-credit PR587 certification decision from retained real-audio evidence.

This intentionally does not call Anthropic, Deepgram, or ElevenLabs.
It cannot claim a live end-to-end certification from offline artifacts.
"""
import json
from pathlib import Path

SOURCE = Path("docs/delivery/pr587-stt-control-latency-3980a8d.json")
LOCAL = Path("docs/delivery/pr587-local-control-decoder-rejections.json")
BUDGET_MS = 500
# 48k microphone capture: end-to-end deadline must reserve execution and output cutoff.
OLD_BLOCK_MS = 4096 / 48000 * 1000
NEW_BLOCK_MS = 2048 / 48000 * 1000


def decision():
    source = json.loads(SOURCE.read_text())
    local = json.loads(LOCAL.read_text())
    flux = [t for t in source["trials"] if t["model"] == "flux" and t["case"] == "cancel"]
    assert len(flux) >= 3, "Insufficient pinned Flux cancel repetitions"
    values = [float(t["first_stop_word_ms"]) for t in flux]
    assert all(t["pcm_sha256"] == flux[0]["pcm_sha256"] for t in flux)
    local_decisions = local["decisions"]
    unsafe = any("falsely" in d.lower() for d in local_decisions.values())
    missing_margin = any(v >= BUDGET_MS for v in values)
    # Capture-block time savings are a theoretical transport bound, not observed
    # provider improvement. Do NOT subtract these from historical provider readings:
    # those readings used a separate replay transport, not the browser microphone.
    return {
        "status": "BLOCKED" if missing_margin or unsafe else "NEEDS_FULL_RUNTIME_CERTIFICATION",
        "certified": False,
        "paid_provider_calls": 0,
        "cutoff_reference": "audio_input_start",
        "cutoff_limit_ms": BUDGET_MS,
        "historical_flux_cancel_recognition_ms": values,
        "historical_flux_recognition_exceeds_budget": missing_margin,
        "historical_local_false_positive": unsafe,
        "browser_capture_block_ms_before": round(OLD_BLOCK_MS, 3),
        "browser_capture_block_ms_after": round(NEW_BLOCK_MS, 3),
        "browser_capture_theoretical_max_reduction_ms": round(OLD_BLOCK_MS - NEW_BLOCK_MS, 3),
        "observed_end_to_end_ms": None,
        "runtime_unauthorized_write_audit": "NOT_RUN",
        "reason": "Offline traces cannot establish improved real PCM-to-cancellation latency or safe decoder generalization",
    }


if __name__ == "__main__":
    print(json.dumps(decision(), indent=2))
    assert decision()["status"] == "BLOCKED", "Unexpected candidate promotion: review evidence"
