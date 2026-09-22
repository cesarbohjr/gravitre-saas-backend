#!/usr/bin/env python3
"""Controlled model-tier comparison on synthetic compiled tasks. No customer data."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "audits" / "gravitre-model-tier-benchmark.json"

TASKS = [
    ("simple_conversation", "Reply in one short sentence: greet a business operator named Alex."),
    (
        "complex_business_reasoning",
        "A CRM shows 25 open deals totaling $1.2M, 8 with no activity in 21 days, "
        "and support tickets up 40% on the same accounts. List 3 ranked risks and one "
        "next action each. Do not invent customer names.",
    ),
    (
        "tool_selection",
        "User said: Show my deals. Choose ONE action key from: hubspot.deals.list, "
        "gmail.messages.list, ga4.run_report. Reply with JSON {action_key, reason}.",
    ),
    (
        "ambiguous_entity",
        "User said: Send Sarah a summary. What must be resolved before a WRITE? "
        "JSON {needs: string[], must_not_guess: true}.",
    ),
    (
        "multi_source_synthesis",
        "Given: HubSpot 25 deals; GA4 last-month sessions unknown (pending_auth). "
        "Write 4 sentences a CEO can trust. Mark unknown vs known.",
    ),
    (
        "safe_write_compilation",
        "User: Create a HubSpot contact for the CEO of Acme. Compile JSON "
        "{write_allowed:false, missing_fields:[], pending_action:true} if unsafe.",
    ),
    (
        "evidence_verification",
        "Observation: hubspot.deals.list success true result_count 25 empty false. "
        "May we claim 'pipeline is healthy'? Answer yes/no and why in 2 sentences.",
    ),
    (
        "voice_appropriate",
        "Same facts as 25 deals count-only. Write a spoken reply under 25 words, no markdown.",
    ),
]


def load_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                merged.update({k: v for k, v in dotenv_values(p, encoding=enc).items() if v})
                break
            except UnicodeDecodeError:
                continue
    merged.update({k: v for k, v in os.environ.items() if v and k not in merged})
    return merged


def score(task_id: str, text: str) -> dict:
    t = (text or "").strip()
    low = t.lower()
    checks: dict[str, bool] = {"nonempty": bool(t)}
    if task_id == "tool_selection":
        checks["hubspot_deals_list"] = "hubspot.deals.list" in low
        checks["jsonish"] = "{" in t
    if task_id == "ambiguous_entity":
        checks["does_not_invent_email"] = "@" not in t
        checks["asks_identity"] = any(w in low for w in ("email", "who", "missing", "resolve"))
    if task_id == "evidence_verification":
        checks["rejects_healthy"] = "no" in low[:40] or "not" in low
    if task_id == "voice_appropriate":
        checks["short"] = len(t.split()) <= 30
        checks["no_markdown"] = "**" not in t and "#" not in t
    if task_id == "multi_source_synthesis":
        checks["marks_unknown"] = "unknown" in low or "pending" in low or "not connected" in low
        checks["uses_25"] = "25" in t
    if task_id == "safe_write_compilation":
        checks["write_false_or_pending"] = "false" in low or "pending" in low
    return {"passed": all(checks.values()) if checks else bool(t), "checks": checks}


def main() -> int:
    env = load_env()
    key = env.get("OPENAI_API_KEY") or env.get("OPENAI_KEY")
    report = {
        "probe": "model_tier_benchmark_synthetic",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "note": "Direct OpenAI chat, not production kernel, not live connectors.",
        "models": ["gpt-5.4-mini", "gpt-5.5"],
        "runs": [],
    }
    if not key:
        report["status"] = "UNKNOWN"
        report["reason"] = "OPENAI_API_KEY not available in local env"
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0

    from openai import OpenAI

    client = OpenAI(api_key=key)
    for model in report["models"]:
        for task_id, prompt in TASKS:
            t0 = time.perf_counter()
            err = None
            text = ""
            usage = {}
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are Gravitre. Be precise. Do not invent customers or metrics.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_completion_tokens=400,
                )
                text = (resp.choices[0].message.content or "") if resp.choices else ""
                if resp.usage:
                    usage = {
                        "input_tokens": getattr(resp.usage, "prompt_tokens", None),
                        "output_tokens": getattr(resp.usage, "completion_tokens", None),
                        "cached_tokens": getattr(
                            getattr(resp.usage, "prompt_tokens_details", None),
                            "cached_tokens",
                            None,
                        ),
                    }
            except Exception as exc:  # noqa: BLE001
                err = f"{type(exc).__name__}: {exc}"[:240]
            ms = int((time.perf_counter() - t0) * 1000)
            sc = score(task_id, text)
            report["runs"].append(
                {
                    "model": model,
                    "task": task_id,
                    "latency_ms": ms,
                    "usage": usage,
                    "error": err,
                    "excerpt": text[:400],
                    "score": sc,
                }
            )
    by_model: dict[str, list] = {}
    for r in report["runs"]:
        by_model.setdefault(r["model"], []).append(r)
    report["summary"] = {
        m: {
            "n": len(rs),
            "pass": sum(1 for x in rs if x["score"]["passed"] and not x["error"]),
            "errors": sum(1 for x in rs if x["error"]),
            "p50_latency_ms": sorted(x["latency_ms"] for x in rs)[len(rs) // 2] if rs else None,
        }
        for m, rs in by_model.items()
    }
    report["status"] = "LIVE_TEST_VERIFIED"
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": report["summary"], "wrote": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
