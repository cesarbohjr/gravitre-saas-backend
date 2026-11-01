"""Fail-closed qualification of a trained local acoustic keyword spotter.

A generic pre-trained wake-word detector is NOT a cancellation model. We require
a phrase-specific, hash-pinned asset and an independently labeled, complete
recorded-audio corpus before any acoustic qualification or side effects.
"""
import argparse
import hashlib
import json
from pathlib import Path

TARGET_MS = 350
DEADLINE_MS = 500
REQUIRED = frozenset(("task_cancel", "negation", "speech_stop", "backchannel", "confusable", "ordinary"))
REPETITIONS = 3


def inspect_manifest(manifest, root):
    errors = []
    model = manifest.get("model", {})
    asset = root / str(model.get("path", "missing.onnx"))
    digest = str(model.get("sha256", ""))
    if not asset.is_file() or len(digest) != 64:
        errors.append("trained_model_asset_missing_or_unpinned")
    elif hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
        errors.append("trained_model_checksum_mismatch")
    if model.get("trained_phrase") != "gravitre cancel task":
        errors.append("model_not_trained_for_distinct_cancel_command")
    items = manifest.get("recordings", [])
    labels = {item.get("label") for item in items}
    errors.extend("missing_label:" + x for x in sorted(REQUIRED - labels))
    if not items:
        errors.append("recording_manifest_empty")
    if len(items) < 12:
        errors.append("insufficient_independent_recordings")
    for item in items:
        rel = str(item.get("path", ""))
        file = root / rel
        if not file.is_file() or len(item.get("sha256", "")) != 64:
            errors.append("recording_missing_or_unpinned:" + rel)
        elif hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]:
            errors.append("recording_checksum_mismatch:" + rel)
    return errors


def evaluate_trials(trials, required_repetitions=REPETITIONS):
    failures = []
    groups = {}
    for row in trials:
        groups.setdefault(row.get("recording_sha256"), []).append(row)
        if row.get("error_type"):
            failures.append("decode_error")
        if row.get("label") == "task_cancel":
            val = row.get("detection_wall_ms")
            if not isinstance(val, (float, int)) or val > TARGET_MS or val < 0:
                failures.append("missed_or_late_positive")
        elif row.get("fired"):
            failures.append("false_task_cancel")
    if not trials:
        failures.append("no_real_acoustic_trials")
    if any(len(rows) < required_repetitions for rows in groups.values()):
        failures.append("insufficient_repetitions")
    if not all(any(x.get("label") == label for x in trials) for label in REQUIRED):
        failures.append("incomplete_negative_or_positive_corpus")
    return sorted(set(failures))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="acceptance-assets/pr587-kws-manifest.json")
    ap.add_argument("--output", default="acceptance-results/pr587-kws-qualification.json")
    args = ap.parse_args()
    path = Path(args.manifest)
    errors = ["qualified_trained_kws_model_and_corpus_not_supplied"]
    if path.is_file():
        manifest = json.loads(path.read_text())
        errors = inspect_manifest(manifest, path.parent)
        # Future acoustic adapter must supply actual measured trials, not text matches.
        trials = manifest.get("acoustic_trials", [])
        errors.extend(evaluate_trials(trials))
    report = {"status": "BLOCKED" if errors else "ACOUSTIC_CANDIDATE_ELIGIBLE_FOR_ISOLATED_RUNTIME_TESTS",
              "certified": False, "runtime_changed": False,
              "recognition_target_ms": TARGET_MS, "end_to_end_limit_ms": DEADLINE_MS,
              "required_repetitions_per_recording": REPETITIONS, "paid_provider_calls": 0,
              "blockers": sorted(set(errors))}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
