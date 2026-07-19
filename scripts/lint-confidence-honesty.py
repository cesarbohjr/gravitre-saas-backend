#!/usr/bin/env python3
"""CI lint: bare confidence/score float literals must use Module C labeling.

Fails when backend/app introduces an assignment like ``confidence = 0.65`` (or
``ml_confidence=0.45``, ``"confidence": 0.8``) without a nearby call to the
shared ``label_confidence`` / ``estimated_confidence`` helper (or an explicit
``confidence_is_estimate`` / ``confidenceIsEstimate`` stamp within ±12 lines).

Existing debt is grandfathered in ``scripts/confidence-honesty-baseline.txt``.
New findings (or findings that move to a new line/path) fail CI — that is the
durable fix for the tenth unlabeled surface.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "backend" / "app"
BASELINE_PATH = REPO / "scripts" / "confidence-honesty-baseline.txt"

# Bare float in (0,1] assigned to confidence-shaped names.
ASSIGN = re.compile(
    r"""\b(?P<name>confidence|ml_confidence|score)\s*=\s*(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
DICT_KEY = re.compile(
    r"""["'](?P<name>confidence|ml_confidence)["']\s*:\s*(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
HONEST = re.compile(
    r"""label_confidence|estimated_confidence|computed_confidence|"""
    r"""model_selection_ml_confidence|_heuristic_edge_confidence|"""
    r"""confidence_is_estimate|confidenceIsEstimate|confidence_source|confidenceSource|"""
    r"""confidence-honesty-ok""",
    re.IGNORECASE,
)
# Builders / models that stamp estimate provenance by default or via label_confidence.
LABELED_CONSTRUCTOR = re.compile(
    r"""\b(MesonSuggestion|MesonInterpretResult|MesonInterpretPayload|Recommendation|_card)\s*\(""",
)

SKIP_FILES = {
    "confidence_honesty.py",
    "confidence_calibrator.py",
    "confidence_scorer.py",  # weight table, not presented scores
}
SKIP_PATH_PARTS = {
    "__pycache__",
}


def _nearby_honest(lines: list[str], idx: int, radius: int = 12) -> bool:
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    window = "\n".join(lines[start:end])
    return bool(HONEST.search(window))


def _inside_labeled_constructor(lines: list[str], idx: int) -> bool:
    depth = 0
    for i in range(idx, -1, -1):
        line = lines[i]
        if depth == 0 and LABELED_CONSTRUCTOR.search(line):
            return True
        depth += line.count(")") - line.count("(")
        if depth > 0:
            return False
        if i < idx - 40:
            return False
    return False


def _file_imports_helper(text: str) -> bool:
    return "confidence_honesty" in text or "_heuristic_edge_confidence" in text


def collect_findings() -> list[str]:
    findings: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        if any(part in SKIP_PATH_PARTS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        rel = path.relative_to(REPO).as_posix()
        uses_helper = _file_imports_helper(text)

        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = ASSIGN.search(line) or DICT_KEY.search(line)
            if not match:
                continue
            val = float(match.group("val"))
            if not (0.0 < val <= 1.0):
                continue
            if "threshold" in line.lower() or "clarification" in line.lower():
                continue
            if "WEIGHTS" in line:
                continue
            if _nearby_honest(lines, idx):
                continue
            if _inside_labeled_constructor(lines, idx):
                continue
            if uses_helper and (
                "_heuristic_edge_confidence(" in line
                or "label_confidence(" in line
                or "estimated_confidence(" in line
                or "computed_confidence(" in line
                or "model_selection_ml_confidence(" in line
            ):
                continue
            findings.append(
                f"{rel}:{idx + 1}: bare {match.group('name')}={match.group('val')}"
            )
    return findings


def load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def main() -> int:
    write_baseline = "--write-baseline" in sys.argv
    findings = collect_findings()
    if write_baseline:
        BASELINE_PATH.write_text(
            "# Grandfathered Module C confidence-honesty debt. Do not grow this list.\n"
            + "\n".join(findings)
            + ("\n" if findings else ""),
            encoding="utf-8",
        )
        print(f"Wrote {len(findings)} findings to {BASELINE_PATH.relative_to(REPO).as_posix()}")
        return 0

    baseline = load_baseline()
    new_findings = [f for f in findings if f not in baseline]
    # Allow baseline entries that were fixed (removed from findings) — do not fail.
    if new_findings:
        print("CONFIDENCE_HONESTY_LINT_FAIL")
        print("New unlabeled confidence constants (not in baseline):")
        for line in new_findings:
            print(f"  - {line}")
        print(
            "\nUse app.services.confidence_honesty.label_confidence(value, source=..., is_estimate=...) "
            "or add confidence_is_estimate nearby. Escape hatch: comment confidence-honesty-ok."
        )
        return 1
    print(f"CONFIDENCE_HONESTY_LINT_OK ({len(findings)} grandfathered, 0 new)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
