"""Run a real custom openWakeWord acoustic ONNX model against pinned PCM recordings.

This runner never calls paid providers or dispatches cancellation actions.
Only a separately trained, commercially usable 'gravitre cancel task' model is
eligible; generic bundled wake words are categorically excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from scripts.pr587_kws_qualification import inspect_manifest, evaluate_trials, TARGET_MS, REPETITIONS

RATE = 16000
STEP_SAMPLES = 1280  # 80 ms frames, standard openWakeWord inference input


def pcm_samples(path):
    import numpy as np
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(path),
         "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"],
        check=True, capture_output=True, timeout=60,
    ).stdout
    if len(raw) == 0 or len(raw) % 2:
        raise ValueError("invalid_pcm")
    return np.frombuffer(raw, dtype="<i2")


def run_model(model_path, pcm, threshold):
    from openwakeword.model import Model
    import numpy as np
    engine = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
    engine.reset()
    started = time.perf_counter()
    detection = None
    for offset in range(0, len(pcm), STEP_SAMPLES):
        frame = pcm[offset:offset + STEP_SAMPLES]
        if len(frame) < STEP_SAMPLES:
            frame = np.pad(frame, (0, STEP_SAMPLES - len(frame)))
        # Causally paced replay: don't reward a faster-than-real-time CPU.
        target = started + (offset + STEP_SAMPLES) / RATE
        delay = target - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        predictions = engine.predict(frame)
        if detection is None and predictions and max(predictions.values()) >= threshold:
            detection = round((time.perf_counter() - started) * 1000, 3)
    return detection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--output", default="acceptance-results/pr587-kws-acoustic-results.json")
    args = ap.parse_args()
    manifest_path = Path(args.manifest)
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text())
    errors = inspect_manifest(manifest, root)
    threshold = manifest.get("model", {}).get("threshold")
    if not isinstance(threshold, (int, float)) or not 0 < threshold < 1:
        errors.append("missing_or_invalid_calibrated_threshold")
    rows = []
    if not errors:
        model_path = root / manifest["model"]["path"]
        for entry in manifest["recordings"]:
            for rep in range(REPETITIONS):
                row = {"recording_sha256": entry["sha256"], "label": entry["label"],
                       "repetition": rep + 1}
                try:
                    pcm = pcm_samples(root / entry["path"])
                    ms = run_model(model_path, pcm, threshold)
                    row.update(detection_wall_ms=ms, fired=ms is not None)
                except Exception as exc:
                    row["error_type"] = type(exc).__name__
                rows.append(row)
        errors.extend(evaluate_trials(rows))
    report = {
        "status": "ACOUSTIC_CANDIDATE_ELIGIBLE_FOR_ISOLATED_RUNTIME_TESTS" if not errors else "BLOCKED",
        "certified": False, "runtime_changed": False, "paid_provider_calls": 0,
        "recognition_target_ms": TARGET_MS, "end_to_end_limit_ms": 500,
        "model_sha256": manifest.get("model", {}).get("sha256"),
        "model_type": "openwakeword_custom_onnx", "threshold": threshold,
        "model_phrase": manifest.get("model", {}).get("trained_phrase"),
        "configuration": {"frame_samples": STEP_SAMPLES, "rate_hz": RATE,
                          "repetitions": REPETITIONS, "causal_wall_clock": True},
        "blockers": sorted(set(errors)), "trials": rows,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "trials"}))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
