#!/usr/bin/env python3
"""Chat-turn latency bench through the real shared turn path (scripted model).

Drives ``tests/scenarios/conversation_harness.py``: the text surface through
``POST /api/assistant/chat`` and the voice surface through the Pipecat
cognitive bridge, both into the production turn path (intent gateway, tiers,
classifiers, tool selection, governed tools). Only the edges are faked: the
model is scripted, connectors run in memory, Supabase is in memory.

Simulated vendor latency (in the output's conditions): a public web search
takes ``--web-search-ms`` per call (default 1000) and a Gmail list/get takes
``--gmail-read-ms`` per call (default 150). Everything else is Gravitre's own
pipeline time on this machine, in real wall-clock time, so absolute numbers
depend on the host: compare two revisions on the same host in one sitting
(``scripts/bench_compare.py`` does that).

Each sample is one fresh conversation: a scripted greeting turn, then the
measured turn. Untimed warm-up turns run first on each surface.

Run from ``backend/``::

    python scripts/bench_chat_turns.py --runs 15 --out /tmp/bench/chat

Writes ``results.json`` (samples, aggregates, conditions) and ``results.md``.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@dataclass(frozen=True)
class Turn:
    key: str
    text: str
    expected: str
    # Web searches the turn should make: (min, max); None = unbounded.
    searches: tuple[int, int | None]
    # Connector actions that must not run on this turn (substring match).
    forbidden_actions: tuple[str, ...] = ()


TURNS: tuple[Turn, ...] = (
    Turn("clock", "What time is it?", "Answered without a web search.", (0, 0)),
    Turn("arithmetic", "What's 2 plus 2?", "Answered without a web search.", (0, 0)),
    Turn("own_calendar", "What's on my calendar today?", "No web search for the user's own data.", (0, 0)),
    Turn("own_website", "How did the website do last week?", "No web search for the user's own data.", (0, 0)),
    Turn("definition", "Explain what a conversion is.", "Answered without a web search.", (0, 0)),
    Turn(
        "email_by_name",
        "Send an email to Stephanie on Gmail",
        "No web search; nothing is sent without the user's approval.",
        (0, 0),
        forbidden_actions=("send",),
    ),
    Turn("thanks", "Thanks!", "Answered without a web search.", (0, 0)),
    Turn("news_control", "What's the latest news about OpenAI?", "Control: public news does use web search.", (1, None)),
)


def _brain(call: Any) -> Any:
    """The scripted model: a send tool call when offered one, otherwise a short answer."""
    from tests.scenarios.conversation_harness import Reply

    if call.after_tool:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if name:
        return Reply(tool_calls=[(name, {"to": "stephanie@invented.example"})])
    return Reply(text="Sure.")


async def run_turn(surface: str, text: str, *, web_ms: int, gmail_ms: int) -> dict[str, Any]:
    from tests.scenarios.conversation_harness import ScenarioHarness

    searches: list[float] = []

    async def fake_search(*_a: Any, **_k: Any) -> dict[str, Any]:
        searches.append(time.perf_counter())
        await asyncio.sleep(web_ms / 1000)
        return {"results": []}

    with ScenarioHarness() as h, patch("app.services.web_research.search_web", fake_search):
        h.connected.extend(["gmail", "google_analytics"])
        h.connectors.mailbox.append(
            {
                "id": "m1",
                "labelIds": ["INBOX"],
                "headers": {"From": "Stephanie Khan <stephanie.khan@acme.example>", "To": "Me <me@x.example>"},
            }
        )
        original = h.connectors.executor_for

        def slow_reads(action: str) -> Any:
            run = original(action)

            def _run(ctx: Any, params: dict[str, Any]) -> Any:
                if "gmail" in action and action.endswith((".list", ".get")):
                    time.sleep(gmail_ms / 1000)
                return run(ctx, params)

            return _run

        h.connectors.executor_for = slow_reads
        conv = h.conversation(surface)
        await conv.say("Hi", "Hi! What can I help with?")
        t0 = time.perf_counter()
        result = await conv.say(text, _brain)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "ms": round(elapsed_ms, 1),
            "web_searches": len(searches),
            "brain_calls": len(result.brain_calls),
            "connector_actions": [c.action for c in result.connector_calls],
            "reply_chars": len(result.text or ""),
        }


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 1)


def grade(turn: Turn, sample: dict[str, Any]) -> tuple[bool, list[str]]:
    problems: list[str] = []
    lo, hi = turn.searches
    if sample["web_searches"] < lo or (hi is not None and sample["web_searches"] > hi):
        problems.append(f"web_searches={sample['web_searches']}")
    bad = [a for a in sample["connector_actions"] if any(f in a.lower() for f in turn.forbidden_actions)]
    if bad:
        problems.append("ran:" + ",".join(bad))
    if not sample["reply_chars"]:
        problems.append("empty_reply")
    return not problems, problems


def aggregate(turn: Turn, samples: list[dict[str, Any]]) -> dict[str, Any]:
    ms = [s["ms"] for s in samples]
    passed = [s for s in samples if s["passed"]]
    problems: dict[str, int] = {}
    for s in samples:
        for p in s["problems"]:
            problems[p] = problems.get(p, 0) + 1
    return {
        "n": len(samples),
        "p50_ms": percentile(ms, 0.5),
        "p95_ms": percentile(ms, 0.95),
        "mean_ms": round(sum(ms) / len(ms), 1) if ms else None,
        "min_ms": min(ms) if ms else None,
        "max_ms": max(ms) if ms else None,
        "mean_web_searches": round(sum(s["web_searches"] for s in samples) / len(samples), 2) if samples else None,
        "accuracy": {"n": len(samples), "pass": len(passed), "rate": round(len(passed) / len(samples), 3) if samples else None},
        "problems": problems,
    }


def markdown_report(results: dict[str, Any]) -> str:
    meta, cond = results["meta"], results["conditions"]
    rows = results["turns"]
    n = sum(r["aggregate"]["accuracy"]["n"] for r in rows.values())
    ok = sum(r["aggregate"]["accuracy"]["pass"] for r in rows.values())
    lines = [
        f"# Chat-turn bench: {meta.get('label') or 'unlabelled'}",
        "",
        (
            f"git: {meta.get('git') or 'unknown'} · backend/app tree: {meta.get('app_tree') or 'unknown'} · "
            f"samples per turn: {meta['runs']} (+{meta['warmup']} untimed warm-up per surface) · "
            f"wall time: {meta.get('wall_s')} s"
        ),
        "",
        "## Conditions",
        "",
        f"- Simulated public web search: {cond['web_search_ms']} ms per call; simulated Gmail list/get: {cond['gmail_read_ms']} ms per call.",
        "- Model scripted (no model time); connectors and database in memory; everything else is the production turn path.",
        (
            f"- Real wall-clock time on this host: {meta.get('platform')}, {meta.get('cpu_count')} CPUs, "
            f"Python {meta.get('python')}. Absolute numbers are host-dependent; compare revisions on one host "
            "in one sitting."
        ),
        "- Each sample is a fresh conversation (greeting turn, then the measured turn); turn time is measured around the measured turn only.",
        "",
        "## Results",
        "",
        f"Accuracy over all samples: **{ok}/{n}**" + (f" ({ok / n:.0%})" if n else "") + ".",
        "",
        "| Surface : turn | n | P50 ms | P95 ms | mean ms | min / max ms | mean web searches | accuracy | problems | expected |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, r in rows.items():
        a = r["aggregate"]
        probs = ", ".join(f"{k} ×{v}" for k, v in a["problems"].items()) or "–"
        lines.append(
            f"| {key} | {a['n']} | {a['p50_ms']} | {a['p95_ms']} | {a['mean_ms']} | {a['min_ms']} / {a['max_ms']} | "
            f"{a['mean_web_searches']} | {a['accuracy']['pass']}/{a['accuracy']['n']} | {probs} | {r['expected']} |"
        )
    return "\n".join(lines) + "\n"


def _git(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=BACKEND_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:  # noqa: BLE001
        return None


def _quiet_logs() -> None:
    logging.disable(logging.WARNING)
    with contextlib.suppress(Exception):
        from loguru import logger

        logger.remove()
        logger.add(sys.stderr, level="CRITICAL")


async def _main(args: argparse.Namespace) -> dict[str, Any]:
    wanted = {t.strip() for t in args.turns.split(",") if t.strip()}
    turns = [t for t in TURNS if not wanted or t.key in wanted]
    surfaces = [s.strip() for s in args.surfaces.split(",") if s.strip()]
    kw = {"web_ms": args.web_search_ms, "gmail_ms": args.gmail_read_ms}
    for surface in surfaces:
        for _ in range(args.warmup):
            await run_turn(surface, "What does a CRM do?", **kw)
    out: dict[str, Any] = {}
    for surface in surfaces:
        for turn in turns:
            samples = []
            for i in range(args.runs):
                sample = await run_turn(surface, turn.text, **kw)
                sample["passed"], sample["problems"] = grade(turn, sample)
                sample["i"] = i
                samples.append(sample)
            agg = aggregate(turn, samples)
            out[f"{surface}:{turn.key}"] = {
                "surface": surface,
                "turn": turn.key,
                "text": turn.text,
                "expected": turn.expected,
                "aggregate": agg,
                "samples": samples,
            }
            print(
                f"{surface:5s} {turn.key:14s} n={agg['n']} p50={agg['p50_ms']} p95={agg['p95_ms']} "
                f"searches={agg['mean_web_searches']} pass={agg['accuracy']['pass']}/{agg['accuracy']['n']}",
                flush=True,
            )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=15, help="timed samples per surface and turn (default 15)")
    parser.add_argument("--warmup", type=int, default=1, help="untimed warm-up turns per surface (default 1)")
    parser.add_argument("--out", required=True, help="output directory for results.json and results.md")
    parser.add_argument("--label", default="", help="label for this result set")
    parser.add_argument("--surfaces", default="text,voice", help="comma-separated: text, voice")
    parser.add_argument("--turns", default="", help="comma-separated turn keys (default: all)")
    parser.add_argument("--web-search-ms", type=int, default=1000, help="simulated web search latency per call")
    parser.add_argument("--gmail-read-ms", type=int, default=150, help="simulated Gmail list/get latency per call")
    parser.add_argument("--verbose", action="store_true", help="keep application logs")
    args = parser.parse_args(argv)

    if not args.verbose:
        _quiet_logs()
    import tests.scenarios.conversation_harness  # noqa: F401 - app imports configure logging

    if not args.verbose:
        _quiet_logs()
    started = time.time()
    turns = asyncio.run(_main(args))
    results = {
        "meta": {
            "label": args.label,
            "runs": args.runs,
            "warmup": args.warmup,
            "git": _git("rev-parse", "--short", "HEAD"),
            "app_tree": _git("rev-parse", "HEAD:backend/app"),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
            "wall_s": round(time.time() - started, 1),
        },
        "conditions": {
            "web_search_ms": args.web_search_ms,
            "gmail_read_ms": args.gmail_read_ms,
            "surfaces": args.surfaces,
            "model": "scripted (tests/scenarios/conversation_harness.py FakeOpenAI)",
            "clock": "real wall clock",
        },
        "turns": turns,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
    (out / "results.md").write_text(markdown_report(results))
    print(f"wrote {out / 'results.json'} and {out / 'results.md'} in {results['meta']['wall_s']} s")
    return 0


if __name__ == "__main__":
    for _key, _value in {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_ANON_KEY": "anon-test",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
        "SUPABASE_JWT_SECRET": "jwt-secret-test",
        "OPENAI_API_KEY": "sk-test-openai",
        "GRAVITRE_DROP_BACKGROUND_TASKS": "1",
    }.items():
        os.environ.setdefault(_key, _value)
    raise SystemExit(main())
