#!/usr/bin/env python3
"""CI lint: Module C confidence honesty (STA-331).

Catches unlabeled confidence presentation in backend/app:

1. Direct assignments: ``confidence = 0.65``, ``ml_confidence=0.45``,
   ``"confidence": 0.8``
2. Fallback expressions inventing a score:
   ``…confidence… or 0.5``, ``get("confidence") or 0.65``,
   ``float(x or 0.5)`` when the line mentions confidence
3. Unannotated trust envelopes: ``wrap_response(`` call sites that pass a
   confidence-shaped argument without nearby estimate/source provenance
   (``confidence_is_estimate`` / ``confidence_source`` / ``annotate_confidence`` /
   ``label_confidence``)

Escape hatch: comment ``confidence-honesty-ok`` within ±12 lines.
Grandfathered debt (shrinking toward zero) lives in
``scripts/confidence-honesty-baseline.txt``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = REPO / "backend" / "app"
BASELINE_PATH = REPO / "scripts" / "confidence-honesty-baseline.txt"
REPORT_PATH = REPO / "docs" / "delivery" / "confidence-honesty-debt.json"

ASSIGN = re.compile(
    r"""\b(?P<name>confidence|ml_confidence|score)\s*=\s*(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
DICT_KEY = re.compile(
    r"""["'](?P<name>confidence|ml_confidence)["']\s*:\s*(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
# Invented score via `or 0.x` on a confidence-shaped expression.
FALLBACK = re.compile(
    r"""(?P<ctx>confidence|ml_confidence)"""
    r"""[^;\n]{0,80}?"""
    r"""\bor\s+(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
FALLBACK_GET = re.compile(
    r"""\.get\(\s*["'](?:confidence|ml_confidence|classification_confidence)["']"""
    r"""[^)]*\)\s*or\s+(?P<val>0\.\d+)\b""",
    re.IGNORECASE,
)
WRAP_CALL = re.compile(r"""\bwrap_response\s*\(""")
HONEST = re.compile(
    r"""label_confidence|estimated_confidence|computed_confidence|"""
    r"""model_selection_ml_confidence|_heuristic_edge_confidence|annotate_confidence|"""
    r"""confidence_is_estimate|confidenceIsEstimate|confidence_source|confidenceSource|"""
    r"""confidence-honesty-ok""",
    re.IGNORECASE,
)
LABELED_CONSTRUCTOR = re.compile(
    r"""\b(MesonSuggestion|MesonInterpretResult|MesonInterpretPayload|Recommendation|_card)\s*\(""",
)

SKIP_FILES = {
    "confidence_honesty.py",
    "confidence_calibrator.py",
    "confidence_scorer.py",
    "ai_trust_layer.py",  # envelope authority — stamps provenance itself
}
SKIP_PATH_PARTS = {"__pycache__"}


def _nearby_honest(lines: list[str], idx: int, radius: int = 12) -> bool:
    start = max(0, idx - radius)
    end = min(len(lines), idx + radius + 1)
    return bool(HONEST.search("\n".join(lines[start:end])))


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


def _wrap_block_has_confidence(lines: list[str], start: int) -> tuple[bool, int]:
    """Return (mentions_confidence, end_idx) for a wrap_response( call starting at start."""
    depth = 0
    saw_conf = False
    end = start
    for i in range(start, min(len(lines), start + 80)):
        line = lines[i]
        if re.search(r"\bconfidence\s*=", line, re.I) or '"confidence"' in line or "'confidence'" in line:
            saw_conf = True
        depth += line.count("(") - line.count(")")
        end = i
        if i > start and depth <= 0:
            break
    return saw_conf, end


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

            # --- 1) direct assign / dict ---
            match = ASSIGN.search(line) or DICT_KEY.search(line)
            if match:
                val = float(match.group("val"))
                if 0.0 < val <= 1.0:
                    if not (
                        "threshold" in line.lower()
                        or "clarification" in line.lower()
                        or "WEIGHTS" in line
                        or _nearby_honest(lines, idx)
                        or _inside_labeled_constructor(lines, idx)
                        or (
                            uses_helper
                            and (
                                "_heuristic_edge_confidence(" in line
                                or "label_confidence(" in line
                                or "estimated_confidence(" in line
                                or "computed_confidence(" in line
                                or "model_selection_ml_confidence(" in line
                            )
                        )
                    ):
                        findings.append(
                            f"{rel}:{idx + 1}: bare {match.group('name')}={match.group('val')}"
                        )

            # --- 2) fallback inventing a score ---
            fb = FALLBACK.search(line) or FALLBACK_GET.search(line)
            if fb and not _nearby_honest(lines, idx):
                # Skip threshold-style clarifiers
                if "threshold" not in line.lower():
                    findings.append(
                        f"{rel}:{idx + 1}: fallback invents confidence or {fb.group('val')}"
                    )

            # --- 3) wrap_response without provenance ---
            if WRAP_CALL.search(line):
                saw_conf, end = _wrap_block_has_confidence(lines, idx)
                if saw_conf:
                    window = "\n".join(lines[idx : end + 1])
                    nearby = "\n".join(lines[max(0, idx - 8) : end + 8])
                    if not HONEST.search(window) and not HONEST.search(nearby):
                        findings.append(
                            f"{rel}:{idx + 1}: wrap_response confidence without estimate/source"
                        )

    # stable unique
    seen: set[str] = set()
    out: list[str] = []
    for f in findings:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def write_debt_report(findings: list[str], baseline: set[str]) -> None:
    import json
    from datetime import datetime, timezone

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    grandfathered = len([f for f in findings if f in baseline])
    payload = {
        "generated_at": now,
        "active_findings": len(findings),
        "grandfathered_remaining": grandfathered,
        "baseline_entries": len(baseline),
        "new_ungrandfathered": [f for f in findings if f not in baseline],
        "fixed_since_baseline": sorted(baseline - set(findings)),
        "findings": findings,
        "target": 0,
        "note": "Module C confidence-honesty debt - trend toward zero. Shrink baseline; never grow it.",
    }
    REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Append-only history so CI / ops can chart debt toward zero over time.
    history_path = REPORT_PATH.with_name("confidence-honesty-debt-history.jsonl")
    history_row = {
        "generated_at": now,
        "active_findings": len(findings),
        "grandfathered_remaining": grandfathered,
        "baseline_entries": len(baseline),
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(history_row) + "\n")


def main() -> int:
    write_baseline = "--write-baseline" in sys.argv
    report_only = "--report" in sys.argv
    findings = collect_findings()
    baseline = load_baseline()
    write_debt_report(findings, baseline)

    if write_baseline:
        BASELINE_PATH.write_text(
            "# Grandfathered Module C confidence-honesty debt. Shrink toward zero — do not grow.\n"
            + "\n".join(findings)
            + ("\n" if findings else ""),
            encoding="utf-8",
        )
        print(f"Wrote {len(findings)} findings to {BASELINE_PATH.relative_to(REPO).as_posix()}")
        print(f"Debt report -> {REPORT_PATH.relative_to(REPO).as_posix()}")
        return 0

    if report_only:
        print(f"active_findings={len(findings)} grandfathered_in_baseline={len(baseline)}")
        for line in findings:
            tag = "BASELINE" if line in baseline else "NEW"
            print(f"  [{tag}] {line}")
        return 0

    new_findings = [f for f in findings if f not in baseline]
    if new_findings:
        print("CONFIDENCE_HONESTY_LINT_FAIL")
        print("New unlabeled confidence patterns (not in baseline):")
        for line in new_findings:
            print(f"  - {line}")
        print(
            "\nUse app.services.confidence_honesty.label_confidence / annotate_confidence, "
            "or pass confidence_is_estimate+confidence_source into wrap_response. "
            "Escape hatch: comment confidence-honesty-ok."
        )
        return 1
    print(
        f"CONFIDENCE_HONESTY_LINT_OK "
        f"(active={len(findings)}, grandfathered={len([f for f in findings if f in baseline])}, new=0)"
    )
    print(f"Debt report -> {REPORT_PATH.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
