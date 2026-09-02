"""Why did every live grounding verdict report assessorRan=False?

assessorRan is confidence_source == "model". False means validate_grounded_answer
did NOT return a model judgement — it fell through to the permissive default
{is_valid: True, confidence 0.5, source heuristic}. That is a fail-open, and a
fail-open validator is indistinguishable from no validator at all.

There are exactly two ways to reach that default:
  A. the router call raised, and the broad `except Exception` swallowed it
  B. the call succeeded but _JSON_BLOCK did not match the response body

This distinguishes them by calling the real function with a realistic
tool-derived payload and reporting the raw model output. No production data is
read and nothing is written.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import dotenv_values  # noqa: E402


def load_env() -> None:
    import os

    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


TOOL_CALL = {
    "tool": "hubspot_search_deals",
    "result": {
        "success": True,
        "count": 49,
        "deals": [{"name": f"Deal {i}", "amount": None} for i in range(10)],
    },
}
DOCS = [
    {"source": "playbook.md", "content": "Renewals are handled by the AE team."},
    {"source": "handbook.pdf", "content": "Refund policy is 30 days."},
]
ANSWER = "You have 49 open deals in HubSpot right now."


async def main() -> int:
    load_env()

    from app.services import answer_validator
    from app.services.answer_validator import build_evidence, validate_grounded_answer

    evidence = build_evidence(DOCS, [TOOL_CALL])
    print(f"evidence items: {len(evidence)} -> {[e['kind'] for e in evidence]}\n")

    raw: dict[str, object] = {}
    original_router = answer_validator.get_model_router

    def _spy():
        router = original_router()
        real_complete = router.complete

        async def _complete(**kwargs):
            raw["prompt_chars"] = len(str(kwargs.get("prompt") or ""))
            try:
                resp = await real_complete(**kwargs)
            except Exception as exc:  # noqa: BLE001
                raw["exception"] = f"{type(exc).__name__}: {exc}"
                raise
            raw["content"] = getattr(resp, "content", None)
            return resp

        router.complete = _complete  # type: ignore[assignment]
        return router

    answer_validator.get_model_router = _spy  # type: ignore[assignment]
    try:
        result = await validate_grounded_answer(ANSWER, DOCS, tool_calls=[TOOL_CALL])
    finally:
        answer_validator.get_model_router = original_router  # type: ignore[assignment]

    print(f"prompt chars      : {raw.get('prompt_chars')}")
    if "exception" in raw:
        print(f"\nCAUSE A — the router call RAISED:\n  {raw['exception']}")
    else:
        content = raw.get("content")
        print(f"raw model content : {content!r}")
        matched = answer_validator._JSON_BLOCK.search(str(content or ""))
        print(f"_JSON_BLOCK match : {bool(matched)}")
        if matched:
            print(f"  matched text    : {matched.group(0)!r}")
            try:
                print(f"  parses as JSON  : {json.loads(matched.group(0))}")
            except Exception as exc:  # noqa: BLE001
                print(f"  CAUSE B — matched text does not parse: {exc}")
        else:
            print("  CAUSE B — the response contains no {...} block the regex accepts")

    print(f"\nresult            : {json.dumps(result, indent=2, default=str)}")
    print(
        f"\nassessorRan would be: {result.get('confidence_source') == 'model'}"
        "   (False = fail-open, the bug being diagnosed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
