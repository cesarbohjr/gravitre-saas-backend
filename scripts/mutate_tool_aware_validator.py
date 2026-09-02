"""Mutation harness for the tool-aware grounding validator.

Every mutation below reverts one specific part of the fix. A test suite that
does not fail on all of them is not actually protecting the behaviour it claims
to protect. Run from backend/.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

V = pathlib.Path("app/services/answer_validator.py")
A = pathlib.Path("app/operators/agent_intelligence.py")
TESTS = [
    "tests/services/test_tool_aware_grounding_validator.py",
    "tests/operators/test_finalize_passes_tool_evidence.py",
]

MUTATIONS: list[tuple[str, pathlib.Path, str, str]] = [
    (
        "validator ignores tool_calls again",
        V,
        "evidence = build_evidence(retrieved_context, tool_calls)",
        "evidence = build_evidence(retrieved_context, None)",
    ),
    (
        "build_evidence drops all tool results",
        V,
        "for call in tool_calls or []:",
        "for call in []:",
    ),
    (
        "failed tool results reported as success",
        V,
        'status = "SUCCESS" if success else ("FAILED" if success is not None else "UNKNOWN")',
        'status = "SUCCESS"',
    ),
    (
        "tool evidence no longer marked authoritative",
        V,
        "Tool results are authoritative primary evidence.",
        "Tool results are one input among many.",
    ),
    (
        "call site reverts has_context to rag-only",
        A,
        "has_context = bool(rag_sources) or bool(turn_tool_calls)",
        "has_context = bool(rag_sources)",
    ),
    (
        "call site stops passing tool_calls to validator",
        A,
        """                content,
                rag_sources,
                tool_calls=turn_tool_calls,
                confidence_threshold=engine_settings.confidence_threshold,
                org_id=org_id,
                settings=settings,
            )
            if not validation.get("is_valid"):""",
        """                content,
                rag_sources,
                confidence_threshold=engine_settings.confidence_threshold,
                org_id=org_id,
                settings=settings,
            )
            if not validation.get("is_valid"):""",
    ),
    (
        "regeneration loses the tool evidence",
        A,
        """                    rag_sources=rag_sources,
                    tool_calls=turn_tool_calls,""",
        """                    rag_sources=rag_sources,""",
    ),
    (
        "regeneration prompt drops build_evidence",
        A,
        "evidence = build_evidence(rag_sources, tool_calls)",
        "evidence = build_evidence(rag_sources, None)",
    ),
    (
        "audit stops recording evidence kind",
        A,
        '"toolResultCount": len(turn_tool_calls),',
        '"toolResultCount": 0,',
    ),
    (
        "assessorRan back to the string literal",
        A,
        "validation.get(\"confidence_source\") == CONFIDENCE_SOURCE_MODEL",
        'validation.get("confidence_source") == "model"',
    ),
    (
        "fail-open stops reporting its reason",
        V,
        '"validator_fallthrough": fallthrough_reason,',
        '"validator_fallthrough": None,',
    ),
    (
        "model errors no longer distinguished from unparseable",
        V,
        'fallthrough_reason = f"model_error:{type(exc).__name__}"',
        'fallthrough_reason = "unknown"',
    ),
]


def main() -> int:
    caught = 0
    for name, path, old, new in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"{name:48s} -> SKIPPED (anchor not found)")
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header"],
                capture_output=True,
                text=True,
            )
            lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
            tail = lines[-1][:44] if lines else "(no output)"
            verdict = "CAUGHT" if proc.returncode != 0 else "NOT CAUGHT <-- BLIND"
            caught += 1 if proc.returncode != 0 else 0
            print(f"{name:48s} -> {verdict:22s} {tail}")
        finally:
            path.write_text(original, encoding="utf-8")
            assert path.read_text(encoding="utf-8") == original, f"restore failed: {path}"

    print(f"\n{caught}/{len(MUTATIONS)} mutations caught; all sources restored")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
