"""Local time-to-first-word benchmark for text chat (``POST /api/assistant/chat``).

Drives the real FastAPI app in-process (real router, real
``AgentIntelligence.execute_task_streaming``, real guardrails, real composer)
with only the network faked. Every outbound HTTP request is answered by a
deterministic stub at the httpx transport layer, with a fixed delay:

    Supabase (PostgREST / RPC)      SUPABASE_MS   (blocking sleep: a sync call
                                                   on the event loop stalls it,
                                                   exactly as in production)
    OpenAI chat, first token        LLM_TTFT_MS, then LLM_CHUNK_MS per chunk
    OpenAI chat, non-streaming      LLM_TTFT_MS + LLM_CHUNK_MS per chunk
    OpenAI moderation / embeddings  MODERATION_MS / EMBED_MS
    anything else                   OTHER_MS

For each scenario it reports, at p50 over ``--runs`` runs:

    first_sse    first SSE byte (the "start" event)
    first_text   first ``text-delta`` event (the first visible word)
    total        last byte of the response
    llm_calls / sb_calls / sb_on_loop   outbound calls made before the first
                 word; ``sb_on_loop`` counts blocking Supabase calls made on the
                 event-loop thread (each one freezes every other request).

``--trace`` prints, for the last run of each scenario, the timeline of outbound
calls and the brain's own pre-kernel checkpoints.

    python scripts/bench_chat_first_token.py
    python scripts/bench_chat_first_token.py --runs 9 --trace --json out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _k, _v in {
    "SUPABASE_URL": "https://bench.supabase.co",
    "SUPABASE_ANON_KEY": "anon-bench",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-bench",
    "SUPABASE_JWT_SECRET": "jwt-secret-bench",
    "OPENAI_API_KEY": "sk-bench-openai",
    "APP_ENV": "dev",
}.items():
    os.environ.setdefault(_k, _v)
# Never let a real key or host leak into the benchmark.
for _k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "VOYAGE_API_KEY", "REDIS_URL"):
    os.environ.pop(_k, None)

import httpx  # noqa: E402

SUPABASE_MS = 30
LLM_TTFT_MS = 400
LLM_CHUNK_MS = 15
MODERATION_MS = 150
EMBED_MS = 150
OTHER_MS = 200

ORG_ID = "00000000-0000-4000-8000-0000000000aa"
USER_ID = "00000000-0000-4000-8000-0000000000bb"


# --------------------------------------------------------------------------- #
# Outbound call recording
# --------------------------------------------------------------------------- #


@dataclass
class Call:
    kind: str
    label: str
    start_ms: float
    end_ms: float
    on_loop: bool
    where: str = ""


@dataclass
class RunRecorder:
    t0: float = 0.0
    calls: list[Call] = field(default_factory=list)
    loop_thread: int | None = None
    first_text_ms: float | None = None

    def rel(self) -> float:
        return (time.perf_counter() - self.t0) * 1000


REC = RunRecorder()
CAPTURE_WHERE = {"on": False}


def _where() -> str:
    """Innermost app frames that led to an outbound call (for --where)."""
    import traceback

    frames = [
        f
        for f in traceback.extract_stack()
        if "/app/" in f.filename and "bench_chat_first_token" not in f.filename
    ]
    return " < ".join(f"{Path(f.filename).stem}:{f.lineno}:{f.name}" for f in reversed(frames[-3:]))


def _record(kind: str, label: str, start: float) -> None:
    end = REC.rel()
    REC.calls.append(
        Call(
            kind=kind,
            label=label,
            start_ms=start,
            end_ms=end,
            on_loop=threading.get_ident() == REC.loop_thread,
            where=_where() if CAPTURE_WHERE["on"] else "",
        )
    )


# --------------------------------------------------------------------------- #
# Fake Supabase (PostgREST)
# --------------------------------------------------------------------------- #

SEED: dict[str, list[dict[str, Any]]] = {
    "organizations": [{"id": ORG_ID, "name": "Bench Co", "slug": "bench", "plan": "pro"}],
    "org_members": [{"org_id": ORG_ID, "user_id": USER_ID, "role": "owner"}],
}


def _table_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if "rpc" in parts:
        return "rpc:" + parts[-1]
    return parts[-1] if parts else ""


def _fake_supabase(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    table = _table_from_path(path)
    method = request.method
    single = "vnd.pgrst.object" in (request.headers.get("accept") or "")
    if method in ("GET", "HEAD"):
        rows = list(SEED.get(table, []))
        if single:
            if len(rows) == 1:
                return httpx.Response(200, json=rows[0])
            return httpx.Response(
                406,
                json={"code": "PGRST116", "message": "JSON object requested, multiple (or no) rows returned"},
            )
        return httpx.Response(200, json=rows, headers={"content-range": f"0-{max(len(rows) - 1, 0)}/{len(rows)}"})
    if method in ("POST", "PATCH", "PUT"):
        if table.startswith("rpc:"):
            return httpx.Response(200, json=[])
        try:
            body = json.loads(request.content or b"null")
        except ValueError:
            body = None
        rows = body if isinstance(body, list) else ([body] if isinstance(body, dict) else [])
        out = []
        for row in rows:
            row = dict(row)
            row.setdefault("id", str(uuid.uuid4()))
            out.append(row)
        if single:
            return httpx.Response(200, json=out[0] if out else {})
        return httpx.Response(201 if method == "POST" else 200, json=out)
    if method == "DELETE":
        return httpx.Response(200, json=[])
    return httpx.Response(200, json={})


# --------------------------------------------------------------------------- #
# Fake OpenAI
# --------------------------------------------------------------------------- #

STREAM_ANSWERS: dict[str, str] = {}
ACTIVE_ANSWER = {"text": "Happy to help with that."}


def _chunks(text: str) -> list[str]:
    words = text.split(" ")
    return [w + (" " if i < len(words) - 1 else "") for i, w in enumerate(words)]


def _label_for(body: dict[str, Any]) -> str:
    msgs = body.get("messages") or body.get("input") or []
    sys_txt = ""
    if isinstance(msgs, list):
        for m in msgs:
            if isinstance(m, dict) and m.get("role") in ("system", "developer"):
                c = m.get("content")
                sys_txt = c if isinstance(c, str) else json.dumps(c)[:200]
                break
        if not sys_txt and msgs and isinstance(msgs[0], dict):
            c = msgs[0].get("content")
            sys_txt = c if isinstance(c, str) else json.dumps(c)[:200]
    tag = " ".join(sys_txt.split())[:70]
    flags = []
    if body.get("stream"):
        flags.append("stream")
    if body.get("tools"):
        flags.append(f"tools={len(body['tools'])}")
    if body.get("response_format"):
        flags.append("json")
    return f"[{','.join(flags)}] {tag}"


def _wants_json(body: dict[str, Any]) -> bool:
    if body.get("response_format"):
        return True
    for m in body.get("messages") or []:
        c = m.get("content") if isinstance(m, dict) else None
        if isinstance(c, str) and "json" in c.lower():
            return True
    return False


def _completion_json(content: str, model: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-bench",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": max(1, len(content) // 4), "total_tokens": 100},
    }


class _SlowStream(httpx.AsyncByteStream):
    def __init__(self, text: str, model: str) -> None:
        self._text = text
        self._model = model

    async def __aiter__(self):
        await asyncio.sleep(LLM_TTFT_MS / 1000)
        for i, piece in enumerate(_chunks(self._text)):
            if i:
                await asyncio.sleep(LLM_CHUNK_MS / 1000)
            payload = {
                "id": "chatcmpl-bench",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": self._model,
                "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(payload)}\n\n".encode()
        tail = {
            "id": "chatcmpl-bench",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self._model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
        }
        yield f"data: {json.dumps(tail)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    async def aclose(self) -> None:
        return None


async def _fake_openai(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    start = REC.rel()
    if path.endswith("/moderations"):
        await asyncio.sleep(MODERATION_MS / 1000)
        _record("moderation", "", start)
        return httpx.Response(
            200,
            json={
                "id": "modr-bench",
                "model": "omni-moderation-latest",
                "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
            },
        )
    if path.endswith("/embeddings"):
        await asyncio.sleep(EMBED_MS / 1000)
        _record("embedding", "", start)
        body = json.loads(request.content or b"{}")
        inputs = body.get("input")
        n = len(inputs) if isinstance(inputs, list) else 1
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": body.get("model", "text-embedding-3-small"),
                "data": [{"object": "embedding", "index": i, "embedding": [0.01] * 1536} for i in range(n)],
                "usage": {"prompt_tokens": 8, "total_tokens": 8},
            },
        )
    if path.endswith("/chat/completions"):
        body = json.loads(request.content or b"{}")
        model = str(body.get("model") or "gpt-bench")
        label = _label_for(body)
        if body.get("stream"):
            # Recorded at first token, which is what the turn waits for.
            _record("llm_stream", label, start)
            REC.calls[-1].end_ms = start + LLM_TTFT_MS
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                stream=_SlowStream(ACTIVE_ANSWER["text"], model),
            )
        content = "{}" if _wants_json(body) else ACTIVE_ANSWER["text"]
        await asyncio.sleep((LLM_TTFT_MS + LLM_CHUNK_MS * len(_chunks(content))) / 1000)
        _record("llm", label, start)
        return httpx.Response(200, json=_completion_json(content, model))
    await asyncio.sleep(OTHER_MS / 1000)
    _record("openai_other", path, start)
    return httpx.Response(404, json={"error": {"message": "not faked"}})


# --------------------------------------------------------------------------- #
# Transport patch
# --------------------------------------------------------------------------- #


def install_fake_network() -> None:
    def handle_request(self, request: httpx.Request) -> httpx.Response:  # sync (supabase-py)
        start = REC.rel()
        host = request.url.host or ""
        if host.endswith("supabase.co"):
            time.sleep(SUPABASE_MS / 1000)
            resp = _fake_supabase(request)
            _record("supabase", f"{request.method} {_table_from_path(request.url.path)}", start)
            return resp
        time.sleep(OTHER_MS / 1000)
        _record("other_sync", f"{request.method} {host}{request.url.path}", start)
        return httpx.Response(404, json={})

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if host == "api.openai.com":
            return await _fake_openai(request)
        start = REC.rel()
        if host.endswith("supabase.co"):
            await asyncio.sleep(SUPABASE_MS / 1000)
            resp = _fake_supabase(request)
            _record("supabase_async", f"{request.method} {_table_from_path(request.url.path)}", start)
            return resp
        await asyncio.sleep(OTHER_MS / 1000)
        _record("other_async", f"{request.method} {host}{request.url.path}", start)
        return httpx.Response(404, json={})

    httpx.HTTPTransport.handle_request = handle_request  # type: ignore[method-assign]
    httpx.AsyncHTTPTransport.handle_async_request = handle_async_request  # type: ignore[method-assign]


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


@dataclass
class Scenario:
    key: str
    text: str
    answer: str
    history: list[dict[str, str]] = field(default_factory=list)


SCENARIOS = [
    Scenario(
        "small_talk",
        "hey, how's it going?",
        "Doing well, thanks for asking. What can I help you with today?",
    ),
    Scenario(
        "simple_question",
        "What is a good conversion rate for a B2B landing page?",
        "For a B2B landing page, 2 to 5 percent is typical. Above 10 percent is strong, and usually means "
        "the offer and the traffic are well matched. Pages with a single clear call to action and a short "
        "form tend to sit at the top of that range. If you share your current rate and traffic source, I "
        "can tell you where you stand.",
    ),
    Scenario(
        "website_traffic",
        "what's my website traffic",
        "I can't read your traffic yet because no analytics source is connected. Once Google Analytics is "
        "connected I can show sessions, users and the top pages for any date range. It takes about a "
        "minute from the Sources page. Want me to walk you through it?",
    ),
    Scenario(
        "followup_correction",
        "no, last month",
        "Last month needs the same analytics connection, which isn't set up yet. As soon as Google "
        "Analytics is connected I'll pull last month's sessions and compare them with the month before. "
        "It takes about a minute from the Sources page.",
        history=[
            {"role": "user", "content": "what's my website traffic this week"},
            {
                "role": "assistant",
                "content": "I don't have a live analytics source connected yet, so I can't read this week's traffic.",
            },
        ],
    ),
]


# --------------------------------------------------------------------------- #
# ASGI driver
# --------------------------------------------------------------------------- #


async def _drain_background(timeout: float = 5.0) -> None:
    me = asyncio.current_task()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pending = [t for t in asyncio.all_tasks() if t is not me and not t.done()]
        if not pending:
            return
        await asyncio.sleep(0.05)


async def run_turn(app: Any, scenario: Scenario, marks_sink: dict[str, Any]) -> dict[str, Any]:
    conversation_id = str(uuid.uuid4())
    messages = [
        {"id": str(uuid.uuid4()), "role": m["role"], "content": m["content"]} for m in scenario.history
    ] + [{"id": str(uuid.uuid4()), "role": "user", "content": scenario.text}]
    body = json.dumps(
        {"messages": messages, "org_id": ORG_ID, "conversation_id": conversation_id, "mode": "fast"}
    ).encode()
    ACTIVE_ANSWER["text"] = scenario.answer
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/assistant/chat",
        "raw_path": b"/api/assistant/chat",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"bench.local"),
            (b"content-type", b"application/json"),
            (b"authorization", b"Bearer bench"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("bench.local", 80),
    }
    sent = {"done": False}

    async def receive():
        if not sent["done"]:
            sent["done"] = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.sleep(3600)
        return {"type": "http.disconnect"}

    out: dict[str, Any] = {"status": None, "first_sse": None, "first_text": None, "total": None}
    text_parts: list[str] = []
    buf = {"s": ""}

    async def send(message):
        now = REC.rel()
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
        elif message["type"] == "http.response.body":
            chunk = (message.get("body") or b"").decode("utf-8", "replace")
            if chunk and out["first_sse"] is None:
                out["first_sse"] = now
            buf["s"] += chunk
            while "\n\n" in buf["s"]:
                frame, buf["s"] = buf["s"].split("\n\n", 1)
                for line in frame.splitlines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        continue
                    try:
                        ev = json.loads(data)
                    except ValueError:
                        continue
                    if ev.get("type") == "text-delta" and ev.get("delta"):
                        if out["first_text"] is None:
                            out["first_text"] = now
                            REC.first_text_ms = now
                        text_parts.append(ev["delta"])
            if not message.get("more_body"):
                out["total"] = now

    _reset_per_message_caches()
    REC.t0 = time.perf_counter()
    REC.calls = []
    REC.first_text_ms = None
    REC.loop_thread = threading.get_ident()
    marks_sink.clear()
    await app(scope, receive, send)
    out["text"] = "".join(text_parts)
    cutoff = out["first_text"] if out["first_text"] is not None else out["total"] or 0
    before = [c for c in REC.calls if c.start_ms <= cutoff]
    out["llm_calls"] = sum(1 for c in before if c.kind.startswith("llm"))
    out["sb_calls"] = sum(1 for c in before if c.kind.startswith("supabase"))
    out["sb_on_loop"] = sum(1 for c in before if c.kind == "supabase" and c.on_loop)
    out["moderation"] = sum(1 for c in before if c.kind == "moderation")
    out["calls"] = [c.__dict__ for c in REC.calls]
    out["marks"] = {k: v for k, v in marks_sink.items() if not k.startswith("_")}
    await _drain_background()
    return out


def _reset_per_message_caches() -> None:
    """Forget caches keyed on the exact message text between runs.

    Production turns carry a new message every time, so a moderation verdict
    or a model reply cached by text would never hit there; repeated runs of
    the same scenario must not hit it here either. Per-org caches (org
    context, connectors, policies) are left warm, as they are in production
    for an org that chats repeatedly.
    """
    from app.services import ai_guardrails, cache_service
    from app.services.intent_gateway import _RESPONSE_CACHE
    from app.services.model_router import get_model_router

    ai_guardrails._moderation_passed.clear()
    _RESPONSE_CACHE.clear()
    get_model_router()._cache.clear()
    # Embeddings, retrieval and Tier-0 answers, all keyed on the message text.
    cache_service._MEMORY.clear()


def _p50(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals)) if vals else None


async def main_async(args: argparse.Namespace) -> dict[str, Any]:
    install_fake_network()

    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import Settings, get_settings
    from app.main import app
    from app.operators.agent_intelligence import AgentIntelligence

    settings = Settings()
    app.dependency_overrides[get_current_user] = lambda: {"user_id": USER_ID, "email": "bench@example.com"}
    app.dependency_overrides[get_org_context] = lambda: ORG_ID
    app.dependency_overrides[get_settings] = lambda: settings

    marks_sink: dict[str, Any] = {}
    original = AgentIntelligence.execute_task_streaming

    def instrumented(self, **kwargs):  # measurement only: capture the brain's checkpoints
        kwargs.setdefault("latency_marks", marks_sink)
        return original(self, **kwargs)

    AgentIntelligence.execute_task_streaming = instrumented  # type: ignore[method-assign]

    only = set(args.only or [])
    results: dict[str, Any] = {}
    for scenario in SCENARIOS:
        if only and scenario.key not in only:
            continue
        runs = []
        for _ in range(args.runs):
            runs.append(await run_turn(app, scenario, marks_sink))
        last = runs[-1] if args.trace_run == "last" else runs[0]
        summary = {
            "status": last["status"],
            "first_sse_p50": _p50([r["first_sse"] for r in runs]),
            "first_text_p50": _p50([r["first_text"] for r in runs]),
            "total_p50": _p50([r["total"] for r in runs]),
            "first_text_cold": runs[0]["first_text"],
            "llm_calls": last["llm_calls"],
            "sb_calls": last["sb_calls"],
            "sb_on_loop": last["sb_on_loop"],
            "moderation": last["moderation"],
            "answer": last["text"][:160],
            "marks": last["marks"],
        }
        results[scenario.key] = summary
        if args.trace:
            print(f"\n=== {scenario.key}: timeline of last run (ms) ===")
            for c in last["calls"]:
                flag = " ON-LOOP" if c["on_loop"] and c["kind"] == "supabase" else ""
                print(f"  {c['start_ms']:7.0f} -> {c['end_ms']:7.0f}  {c['kind']:<14} {c['label'][:110]}{flag}")
                if c.get("where"):
                    print(f"           {c['where']}")
            print(f"  first_text={last['first_text']} total={last['total']}")
            print(f"  marks={summary['marks']}")
            print("  per-run first_text:", [round(r["first_text"] or -1) for r in runs])
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--where", action="store_true", help="with --trace: show the app frames behind each call")
    parser.add_argument("--trace-run", choices=("first", "last"), default="last")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args()

    import logging

    CAPTURE_WHERE["on"] = bool(args.where)
    logging.disable(logging.WARNING if not os.environ.get("BENCH_LOGS") else logging.NOTSET)
    results = asyncio.run(main_async(args))

    cols = ("first_sse_p50", "first_text_p50", "total_p50", "first_text_cold", "llm_calls", "sb_calls", "sb_on_loop", "moderation")
    print("\nscenario              " + "  ".join(f"{c:>15}" for c in cols))
    for key, row in results.items():
        print(f"{key:<22}" + "  ".join(f"{str(row[c]):>15}" for c in cols))
    for key, row in results.items():
        print(f"  {key}: status={row['status']} answer={row['answer']!r}")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
