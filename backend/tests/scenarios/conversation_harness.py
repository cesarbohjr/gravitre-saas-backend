"""Multi-turn conversation harness over the real shared turn path.

Drives the same brain (``AgentIntelligence.execute_task_streaming``) through
both real entry points:

* text: ``POST /api/assistant/chat`` (FastAPI app, auth overridden),
* voice: ``GravitreCognitiveLLMService._run_gravitre_turn`` (Pipecat bridge).

Only the edges are faked, deterministically:

* the language model is ``FakeOpenAI`` (every OpenAI call goes through
  ``ModelRouter._openai``); each turn scripts what "the model" says,
* connectors are faked at the executor seam (``tool_service._resolve_tool_executor``),
  so preflight, permissions, approvals and the write gate all stay real,
* Supabase is an in-memory, filter-honouring ``ScenarioDB``.

Everything between (intent gateway, tiers, pending/offer classifiers, task
state, the unified live turn, Composer) is production code.
"""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import copy
import json
import re
import uuid
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

ORG = "00000000-0000-4000-8000-00000000a001"
USER = "00000000-0000-4000-8000-00000000c001"

CONNECTED = ["google_analytics", "google_search_console", "hubspot", "asana"]

# Tables whose rows carry conversational state between turns. Everything else
# (audit, telemetry, learning) accepts writes and keeps nothing.
STATEFUL_TABLES = {
    "conversations",
    "conversation_messages",
    "pending_actions",
    "approval_requests",
    "approvals",
    "organization_members",
}


# ---------------------------------------------------------------------------
# In-memory Supabase
# ---------------------------------------------------------------------------


@dataclass
class _Resp:
    data: Any
    error: Any = None
    count: int | None = None


def _json_path_get(row: dict[str, Any], path: str) -> Any:
    parts = re.split(r"->>?", path)
    value: Any = row
    for part in parts:
        if not isinstance(value, dict):
            return None
        value = value.get(part.strip())
    return value


class _Q:
    """Chainable query; unknown builder methods are accepted and ignored."""

    def __init__(self, db: ScenarioDB, table: str) -> None:
        self.db = db
        self.table = table
        self.op = "select"
        self.payload: Any = None
        self.preds: list[Callable[[dict[str, Any]], bool]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._single = False
        self._maybe_single = False
        self._on_conflict: str | None = None

    # ops
    def select(self, *_a: Any, **_k: Any) -> _Q:
        if self.op not in {"insert", "update", "upsert", "delete"}:
            self.op = "select"
        return self

    def insert(self, payload: Any, **_k: Any) -> _Q:
        self.op, self.payload = "insert", payload
        return self

    def upsert(self, payload: Any, on_conflict: str | None = None, **_k: Any) -> _Q:
        self.op, self.payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def update(self, payload: Any, **_k: Any) -> _Q:
        self.op, self.payload = "update", payload
        return self

    def delete(self, **_k: Any) -> _Q:
        self.op = "delete"
        return self

    # filters
    def _add(self, fn: Callable[[dict[str, Any]], bool]) -> _Q:
        self.preds.append(fn)
        return self

    def eq(self, col: str, val: Any) -> _Q:
        return self._add(lambda r: _json_path_get(r, col) == val if "->" in col else r.get(col) == val)

    def neq(self, col: str, val: Any) -> _Q:
        return self._add(lambda r: r.get(col) != val)

    def in_(self, col: str, vals: Any) -> _Q:
        values = list(vals or [])
        return self._add(lambda r: r.get(col) in values)

    def is_(self, col: str, val: Any) -> _Q:
        if str(val).lower() == "null":
            return self._add(lambda r: r.get(col) is None)
        return self

    def filter(self, col: str, op: str, val: Any) -> _Q:
        if op == "eq":
            return self._add(lambda r: str(_json_path_get(r, col)) == str(val))
        return self

    def _cmp(self, col: str, val: Any, fn: Callable[[Any, Any], bool]) -> _Q:
        def pred(r: dict[str, Any]) -> bool:
            have = r.get(col)
            if have is None:
                return False
            try:
                return fn(str(have), str(val))
            except Exception:  # noqa: BLE001
                return False

        return self._add(pred)

    def gt(self, col: str, val: Any) -> _Q:
        return self._cmp(col, val, lambda a, b: a > b)

    def gte(self, col: str, val: Any) -> _Q:
        return self._cmp(col, val, lambda a, b: a >= b)

    def lt(self, col: str, val: Any) -> _Q:
        return self._cmp(col, val, lambda a, b: a < b)

    def lte(self, col: str, val: Any) -> _Q:
        return self._cmp(col, val, lambda a, b: a <= b)

    def order(self, col: str, desc: bool = False, **_k: Any) -> _Q:
        self._order = (col, bool(desc))
        return self

    def limit(self, n: int, **_k: Any) -> _Q:
        self._limit = int(n)
        return self

    def range(self, start: int, end: int) -> _Q:
        self._limit = int(end) - int(start) + 1
        return self

    def single(self) -> _Q:
        self._single = True
        return self

    def maybe_single(self) -> _Q:
        self._maybe_single = True
        return self

    @property
    def not_(self) -> _Q:
        return self

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: self

    def _match(self, row: dict[str, Any]) -> bool:
        return all(p(row) for p in self.preds)

    def execute(self) -> _Resp:
        self.db.log.append((self.op, self.table))
        if self.table not in STATEFUL_TABLES:
            # Telemetry, audit and learning tables: accept writes, keep nothing.
            if self.op in {"insert", "upsert"}:
                batch = self.payload if isinstance(self.payload, list) else [self.payload]
                return _Resp([{"id": str(uuid.uuid4()), **(r if isinstance(r, dict) else {})} for r in batch])
            return _Resp(None if (self._single or self._maybe_single) else [])
        rows = self.db.tables.setdefault(self.table, [])
        if self.op == "select":
            found = [copy.deepcopy(r) for r in rows if self._match(r)]
            if self._order:
                col, desc = self._order
                found.sort(key=lambda r: str(r.get(col) or ""), reverse=desc)
            if self._limit is not None:
                found = found[: self._limit]
            if self._single or self._maybe_single:
                return _Resp(found[0] if found else None)
            return _Resp(found)
        if self.op in {"insert", "upsert"}:
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for raw in batch:
                row = copy.deepcopy(raw) if isinstance(raw, dict) else {}
                row.setdefault("id", str(uuid.uuid4()))
                existing = next((r for r in rows if r.get("id") == row["id"]), None)
                if existing is not None:
                    existing.update(row)
                    out.append(copy.deepcopy(existing))
                else:
                    rows.append(row)
                    out.append(copy.deepcopy(row))
            return _Resp(out)
        if self.op == "update":
            changed = []
            for row in rows:
                if self._match(row):
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return _Resp(changed)
        if self.op == "delete":
            keep = [r for r in rows if not self._match(r)]
            gone = [r for r in rows if self._match(r)]
            self.db.tables[self.table] = keep
            return _Resp(gone)
        return _Resp([])


class _Noop:
    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: self

    def execute(self) -> _Resp:
        return _Resp(None)


class ScenarioDB:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.log: list[tuple[str, str]] = []

    def table(self, name: str) -> _Q:
        return _Q(self, name)

    def from_(self, name: str) -> _Q:
        return _Q(self, name)

    def rpc(self, *_a: Any, **_k: Any) -> _Noop:
        return _Noop()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("__"):
            raise AttributeError(name)
        return _Noop()

    def rows(self, table: str, **match: Any) -> list[dict[str, Any]]:
        return [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]


# ---------------------------------------------------------------------------
# Fake language model
# ---------------------------------------------------------------------------

_AUX = contextvars.ContextVar("scenario_aux_call", default="")


@dataclass
class Reply:
    """What the fake model says on one call: text and/or tool calls."""

    text: str = ""
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


@dataclass
class BrainCall:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    aux: str

    @property
    def tool_names(self) -> list[str]:
        out = []
        for tool in self.tools or []:
            fn = tool.get("function") if isinstance(tool, dict) else None
            out.append(str((fn or tool).get("name") or ""))
        return out

    @property
    def last_user(self) -> str:
        for msg in reversed(self.messages or []):
            if msg.get("role") == "user":
                content = msg.get("content")
                return content if isinstance(content, str) else json.dumps(content)
        return ""

    @property
    def after_tool(self) -> bool:
        return bool(self.messages) and self.messages[-1].get("role") == "tool"

    def transcript(self) -> str:
        parts = []
        for msg in self.messages or []:
            content = msg.get("content")
            parts.append(f"{msg.get('role')}: {content if isinstance(content, str) else json.dumps(content)}")
        return "\n".join(parts)


Responder = Callable[[BrainCall], Reply]


def _tool_name_matching(call: BrainCall, *needles: str) -> str | None:
    for name in call.tool_names:
        low = name.lower()
        if all(n in low for n in needles):
            return name
    return None


class Brain:
    """Scripted stand-in for the model. One responder per turn."""

    def __init__(self) -> None:
        self.calls: list[BrainCall] = []
        self.aux_calls: list[BrainCall] = []
        self.responder: Responder = lambda call: Reply(text="Okay.")

    def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Reply:
        call = BrainCall(messages=list(messages or []), tools=list(tools or []), aux=_AUX.get())
        if call.aux:
            self.aux_calls.append(call)
            raise RuntimeError(f"aux model unavailable in scenario harness ({call.aux})")
        self.calls.append(call)
        return self.responder(call)


class _Stream:
    def __init__(self, reply: Reply) -> None:
        self._chunks: list[Any] = []
        if reply.text:
            for piece in re.findall(r"\S+\s*", reply.text):
                self._chunks.append(
                    SimpleNamespace(
                        usage=None,
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=piece, tool_calls=None))],
                    )
                )
        for idx, (name, args) in enumerate(reply.tool_calls):
            self._chunks.append(
                SimpleNamespace(
                    usage=None,
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content=None,
                                tool_calls=[
                                    SimpleNamespace(
                                        index=idx,
                                        id=f"call_{uuid.uuid4().hex[:8]}",
                                        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
                                    )
                                ],
                            )
                        )
                    ],
                )
            )

    def __aiter__(self) -> _Stream:
        return self

    async def __anext__(self) -> Any:
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class _Completions:
    def __init__(self, brain: Brain) -> None:
        self.brain = brain

    async def create(self, **kwargs: Any) -> Any:
        reply = self.brain.respond(kwargs.get("messages") or [], kwargs.get("tools") or [])
        if kwargs.get("stream"):
            return _Stream(reply)
        tool_calls = [
            SimpleNamespace(
                id=f"call_{uuid.uuid4().hex[:8]}",
                type="function",
                function=SimpleNamespace(name=name, arguments=json.dumps(args)),
            )
            for name, args in reply.tool_calls
        ]
        message = SimpleNamespace(
            role="assistant",
            content=reply.text or None,
            tool_calls=tool_calls or None,
            refusal=None,
            model_dump=lambda **_k: {"role": "assistant", "content": reply.text},
        )
        usage = SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0),
        )
        return SimpleNamespace(
            id="chatcmpl-scenario",
            model=str(kwargs.get("model") or "scenario"),
            choices=[SimpleNamespace(index=0, message=message, finish_reason="stop")],
            usage=usage,
        )


class FakeOpenAI:
    def __init__(self, brain: Brain) -> None:
        self.chat = SimpleNamespace(completions=_Completions(brain))
        self.embeddings = SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("no embeddings")))
        self.moderations = SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("no moderation")))


# ---------------------------------------------------------------------------
# Fake connectors
# ---------------------------------------------------------------------------


def _ga_report(
    users: int,
    sessions: int,
    views: int,
    *,
    rows: list[tuple[str, int]] | None = None,
    dimension: str = "pagePath",
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "metricHeaders": [{"name": "activeUsers"}, {"name": "sessions"}, {"name": "screenPageViews"}],
        "totals": [{"metricValues": [{"value": str(users)}, {"value": str(sessions)}, {"value": str(views)}]}],
        "rows": [],
    }
    if rows:
        report["dimensionHeaders"] = [{"name": dimension}]
        report["rows"] = [
            {"dimensionValues": [{"value": path}], "metricValues": [{"value": str(n)}]} for path, n in rows
        ]
    return {"report": report}


@dataclass
class ConnectorCall:
    action: str
    params: dict[str, Any]


class Connectors:
    """Records every connector execution that got past governance."""

    def __init__(self) -> None:
        self.calls: list[ConnectorCall] = []

    def executor_for(self, action: str) -> Callable[[Any, dict[str, Any]], Any]:
        from app.services.tool_types import NormalizedResult

        def _run(_ctx: Any, params: dict[str, Any]) -> NormalizedResult:
            self.calls.append(ConnectorCall(action=action, params=copy.deepcopy(dict(params or {}))))
            low = action.lower()
            if "searchconsole" in low or "search_console" in low:
                data = {"rows": [{"keys": ["/pricing"], "clicks": 320, "impressions": 9100}]}
            elif "analytics" in low:
                dims = [str(d.get("name") if isinstance(d, dict) else d) for d in (params.get("dimensions") or [])]
                if any("page" in d.lower() for d in dims):
                    data = _ga_report(1200, 1500, 4100, rows=[("/pricing", 900), ("/blog/launch", 610)])
                elif any("channel" in d.lower() for d in dims):
                    data = _ga_report(
                        1200,
                        1500,
                        4100,
                        rows=[("Organic Search", 820), ("Direct", 430)],
                        dimension="sessionDefaultChannelGroup",
                    )
                else:
                    data = _ga_report(1200, 1500, 4100)
            elif "task" in low:
                data = {"id": "task-1", "subject": params.get("subject") or params.get("title") or "Follow up"}
            else:
                data = {"ok": True}
            return NormalizedResult(success=True, action=action, data=data)

        return _run

    def actions(self) -> list[str]:
        return [c.action for c in self.calls]


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    surface: str
    user: str
    text: str
    model: str
    brain_calls: list[BrainCall]
    connector_calls: list[ConnectorCall]
    task_state: dict[str, Any]
    events: list[Any] = field(default_factory=list)

    @property
    def brain_called(self) -> bool:
        return bool(self.brain_calls)

    @property
    def brain_tool_offers(self) -> list[str]:
        names: list[str] = []
        for call in self.brain_calls:
            names.extend(call.tool_names)
        return names

    @property
    def pending_task(self) -> dict[str, Any] | None:
        pending = self.task_state.get("pending_task")
        return pending if isinstance(pending, dict) and pending else None


class Conversation:
    """One conversation driven turn by turn on a single surface."""

    def __init__(self, harness: ScenarioHarness, surface: str) -> None:
        self.h = harness
        self.surface = surface
        self.conversation_id = str(uuid.uuid4())
        self.history: list[dict[str, str]] = []
        self.turns: list[TurnResult] = []
        self._voice: Any = None

    async def say(self, text: str, model: Responder | Reply | str | None = None) -> TurnResult:
        if model is None:
            self.h.brain.responder = lambda call: Reply(text="Okay.")
        elif isinstance(model, str):
            self.h.brain.responder = lambda call, _t=model: Reply(text=_t)
        elif isinstance(model, Reply):
            self.h.brain.responder = lambda call, _r=model: _r
        else:
            self.h.brain.responder = model
        brain_before = len(self.h.brain.calls)
        conn_before = len(self.h.connectors.calls)
        if self.surface == "text":
            text_out, model_label, events = await self.h.run_text_turn(self, text)
        else:
            text_out, model_label, events = await self.h.run_voice_turn(self, text)
        state = self.h.task_state(self.conversation_id)
        result = TurnResult(
            surface=self.surface,
            user=text,
            text=text_out,
            model=model_label,
            brain_calls=self.h.brain.calls[brain_before:],
            connector_calls=self.h.connectors.calls[conn_before:],
            task_state=state,
            events=events,
        )
        self.history.append({"role": "user", "content": text})
        if text_out:
            self.history.append({"role": "assistant", "content": text_out})
        self.turns.append(result)
        return result


    async def interrupt_before_reply(self, text: str) -> None:
        """Voice: the user talks over Gravitre before any of the answer is spoken."""
        await self.h.run_interrupted_voice_turn(self, text, after_speech=False)

    async def interrupt_mid_reply(self, text: str) -> None:
        """Voice: the user talks over Gravitre once part of the answer was spoken."""
        await self.h.run_interrupted_voice_turn(self, text, after_speech=True)


class ScenarioHarness:
    """One org, one user. ``role`` is the user's org role: an ``admin`` can
    approve their own writes in chat; a ``member`` has writes queued for an
    admin's approval."""

    def __init__(self, *, role: str = "admin") -> None:
        self.db = ScenarioDB()
        self.db.tables["organization_members"] = [{"org_id": ORG, "user_id": USER, "role": role}]
        self.brain = Brain()
        self.connectors = Connectors()
        self.connected = list(CONNECTED)
        self._stack = ExitStack()
        self.settings: Any = None
        self.app: Any = None

    # -- lifecycle -------------------------------------------------------
    def __enter__(self) -> ScenarioHarness:
        from app.config import Settings

        self.settings = Settings(
            app_env="dev",
            supabase_url="https://test.supabase.co",
            supabase_anon_key="anon-test",
            supabase_service_role_key="service-role-test",
            supabase_jwt_secret="jwt-secret-test",
            openai_api_key="sk-test-openai",
            anthropic_api_key="",
            google_api_key="",
            ai_moderation_enabled=False,
            unified_turn_live_enabled=True,
        )
        self._install()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stack.close()
        import app.services.model_router as model_router_module

        model_router_module._model_router_singleton = None

    def _p(self, target: str, new: Any) -> None:
        self._stack.enter_context(patch(target, new))

    def _install(self) -> None:
        import app.services.model_router as model_router_module
        from app.services.connector_resource_resolver import ResourceResolution

        settings = self.settings
        db = self.db

        # Settings and DB everywhere: every module's ``create_client`` binding.
        import sys

        import supabase

        import app.main  # noqa: F401 - import the app graph so every binding exists
        from app.core.db import clear_shared_service_clients

        clear_shared_service_clients()
        real_create = supabase.create_client
        fake_create = lambda *_a, **_k: db
        self._p("supabase.create_client", fake_create)
        for name, module in list(sys.modules.items()):
            if name.startswith("app.") and getattr(module, "create_client", None) is real_create:
                self._p(f"{name}.create_client", fake_create)
        self._stack.callback(clear_shared_service_clients)
        import app.config as config_module

        real_get_settings = config_module.get_settings
        fake_settings = lambda: settings
        self._real_get_settings = real_get_settings
        for name, module in list(sys.modules.items()):
            if (name == "app.config" or name.startswith("app.")) and getattr(
                module, "get_settings", None
            ) is real_get_settings:
                self._p(f"{name}.get_settings", fake_settings)

        # Model: one fake client behind the real router.
        router = model_router_module.ModelRouter(settings)
        router._openai = FakeOpenAI(self.brain)
        original_complete = router.complete

        async def _aux_complete(*args: Any, **kwargs: Any) -> Any:
            task_type = kwargs.get("task_type") or (args[0] if args else "")
            token = _AUX.set(str(getattr(task_type, "value", task_type) or "complete"))
            try:
                return await original_complete(*args, **kwargs)
            finally:
                _AUX.reset(token)

        from app.services.providers.base import AllProvidersFailedError

        brain = self.brain

        async def _aux_unavailable(*args: Any, **kwargs: Any) -> Any:
            # Auxiliary model calls (classifiers, rewriters, Composer polish)
            # fail fast, so every routing decision under test is the
            # deterministic one production falls back to.
            task_type = kwargs.get("task_type") or (args[0] if args else "")
            brain.aux_calls.append(
                BrainCall(
                    messages=[{"role": "user", "content": str(kwargs.get("prompt") or "")}],
                    tools=[],
                    aux=str(getattr(task_type, "value", task_type) or "complete"),
                )
            )
            raise AllProvidersFailedError([("openai", "scenario harness: auxiliary model unavailable")])

        del _aux_complete
        router.complete = _aux_unavailable  # type: ignore[method-assign]
        router.prepare_stream = AsyncMock(return_value=None)  # type: ignore[method-assign]
        model_router_module._model_router_singleton = router
        # Singletons that captured an earlier router must pick up this one.
        import app.operators.agent_intelligence as agent_intelligence_module
        import app.operators.react_engine as react_engine_module
        import app.services.chat_connector_execution_service as chat_connector_module
        import app.services.tool_registry as tool_registry_module

        def _drop_singletons() -> None:
            agent_intelligence_module._agent_intelligence_singleton = None
            react_engine_module._react_engine_singleton = None
            # Other suites mutate the shared registry in place (for example
            # ``registry.execute_invoke_action = AsyncMock(...)``); a fresh one
            # keeps every write going through the connector seam below.
            tool_registry_module._tool_registry_singleton = None
            chat_connector_module._chat_connector_execution_service = None

        _drop_singletons()

        self._stack.callback(_drop_singletons)

        # Connectors: org has GA4, Search Console and HubSpot connected.
        connected = self.connected
        self._p(
            "app.connectors.connector_availability_service.list_executable_integrations",
            lambda *_a, **_k: list(connected),
        )
        import app.connectors.connector_availability_service as availability_module

        real_availability = availability_module.list_connector_availability

        def _availability(*_a: Any, **_k: Any) -> list[dict[str, Any]]:
            return [
                {
                    "vendor": vendor,
                    "connector_id": f"conn-{vendor}",
                    "status": "connected",
                    "connected": True,
                    "execution_available": True,
                    "environment": "production",
                }
                for vendor in connected
            ]

        for name, module in list(sys.modules.items()):
            if name.startswith("app.") and getattr(module, "list_connector_availability", None) is real_availability:
                self._p(f"{name}.list_connector_availability", _availability)

        def _resolve(*_a: Any, connector_id: str = "", **_k: Any) -> ResourceResolution:
            vendor = str(connector_id or "").lower()
            rid = {"google_analytics": "123456", "google_search_console": "sc-domain:acme.example"}.get(vendor, "default")
            return ResourceResolution(
                status="resolved",
                connector_id=vendor,
                connection_id=f"conn-{vendor}",
                resource_type="property",
                resource_id=rid,
                display_name="Acme site",
                candidate_count=1,
                resolution_reason="linked_config",
            )

        for target in (
            "app.services.connector_resource_resolver.resolve_resource",
            "app.services.read_preflight.resolve_resource",
            "app.services.analytics_traffic_overview_service.resolve_resource",
            "app.services.write_preflight.resolve_resource",
        ):
            try:
                self._p(target, _resolve)
            except AttributeError:
                pass

        connectors = self.connectors
        self._p(
            "app.services.tool_service._resolve_tool_executor",
            lambda action, ctx=None: connectors.executor_for(action),
        )
        # Background / network edges that are not part of the decision.
        self._p("app.services.mcp_client_service.MCPClientService.get_enabled_tools_for_org", AsyncMock(return_value=[]))
        self._p("app.services.chat_turn_cancel_service.get_redis_client", lambda *_a, **_k: None)

        class _NoEmbeddings:
            class embeddings:
                @staticmethod
                def create(*_a, **_k):
                    raise RuntimeError("embeddings are not available in scenario tests")

        def _no_tool_embeddings(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError("tool embeddings are not available in scenario tests")

        for target, replacement in (
            ("app.rag.embedding._get_sync_openai_client", lambda *_a, **_k: _NoEmbeddings()),
            ("app.rag.tool_retrieval_embedding.embed_tool_retrieval_query_timed", _no_tool_embeddings),
            ("app.rag.tool_retrieval_embedding.embed_tool_retrieval_docs_timed", _no_tool_embeddings),
        ):
            try:
                self._p(target, replacement)
            except AttributeError:
                pass

    # -- state -----------------------------------------------------------
    def task_state(self, conversation_id: str) -> dict[str, Any]:
        rows = self.db.rows("conversations", id=conversation_id)
        if not rows:
            return {}
        return copy.deepcopy(rows[0].get("task_state") or {})

    def conversation(self, surface: str) -> Conversation:
        return Conversation(self, surface)

    # -- text entry ------------------------------------------------------
    async def _text_client(self) -> Any:
        if self.app is None:
            from app.auth.dependencies import (
                get_current_user,
                get_environment_context,
                get_org_context,
            )
            from app.main import app

            _gs = self._real_get_settings

            app.dependency_overrides[get_current_user] = lambda: {"user_id": USER, "email": "scenario@example.com"}
            app.dependency_overrides[get_org_context] = lambda: ORG
            app.dependency_overrides[get_environment_context] = lambda: "production"
            app.dependency_overrides[_gs] = lambda: self.settings
            self._stack.callback(app.dependency_overrides.clear)
            self.app = app
        return self.app

    async def run_text_turn(self, conv: Conversation, text: str) -> tuple[str, str, list[Any]]:
        from httpx import ASGITransport, AsyncClient

        app = await self._text_client()
        captured: dict[str, Any] = {}
        from app.operators.agent_intelligence import AgentIntelligence

        original = AgentIntelligence.execute_task_streaming

        async def _spy(self_: Any, **kwargs: Any):
            captured["kwargs"] = kwargs
            async for event in original(self_, **kwargs):
                from app.operators.stream_events import AssistantStreamComplete

                if isinstance(event, AssistantStreamComplete):
                    captured["complete"] = event
                yield event

        body = {
            "messages": [*conv.history, {"role": "user", "content": text}],
            "conversation_id": conv.conversation_id,
            "mode": "fast",
        }
        lines: list[str] = []
        with patch.object(AgentIntelligence, "execute_task_streaming", _spy):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                async with client.stream("POST", "/api/assistant/chat", json=body) as resp:
                    assert resp.status_code == 200, await resp.aread()
                    async for line in resp.aiter_lines():
                        lines.append(line)
        deltas: list[str] = []
        for line in lines:
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            try:
                payload = json.loads(raw)
            except ValueError:
                continue
            if payload.get("type") == "text-delta":
                deltas.append(str(payload.get("delta") or ""))
        complete = captured.get("complete")
        full = str(getattr(complete, "full_content", "") or "").strip() or "".join(deltas).strip()
        return full, str(getattr(complete, "model", "") or ""), lines

    # -- voice entry -----------------------------------------------------
    def _voice_service(self, conv: Conversation) -> Any:
        if conv._voice is None:
            from app.services.pipecat_voice.cognitive_llm import (
                GravitreCognitiveLLMService,
            )

            llm = GravitreCognitiveLLMService(
                app_settings=self.settings,
                org_id=ORG,
                user_id=USER,
                conversation_id=conv.conversation_id,
            )
            llm.push_frame = AsyncMock()  # type: ignore[method-assign]
            spoken: list[str] = []

            async def _push_llm_text(text: str, *_a: Any, **_k: Any) -> None:
                spoken.append(text)

            llm._push_llm_text = _push_llm_text  # type: ignore[method-assign]
            llm._scenario_spoken = spoken  # type: ignore[attr-defined]
            conv._voice = llm
        return conv._voice

    async def run_interrupted_voice_turn(self, conv: Conversation, text: str, *, after_speech: bool) -> None:
        """Run a voice turn through ``process_frame`` and cancel it like a barge-in does."""
        from pipecat.frames.frames import LLMContextFrame
        from pipecat.processors.aggregators.llm_context import LLMContext
        from pipecat.processors.frame_processor import FrameDirection
        from pipecat.services.llm_service import LLMService

        from app.operators.agent_intelligence import AgentIntelligence

        llm = self._voice_service(conv)
        llm.start_processing_metrics = AsyncMock()  # type: ignore[method-assign]
        llm.stop_processing_metrics = AsyncMock()  # type: ignore[method-assign]
        started = asyncio.Event()
        spoke = asyncio.Event()
        original_push = llm._push_llm_text

        async def _push(text_: str, *a: Any, **k: Any) -> None:
            await original_push(text_, *a, **k)
            spoke.set()

        llm._push_llm_text = _push  # type: ignore[method-assign]
        original = AgentIntelligence.execute_task_streaming

        async def _spy(self_: Any, **kwargs: Any):
            started.set()
            async for event in original(self_, **kwargs):
                yield event
                if not after_speech:
                    # Hold here until the barge-in cancels the turn.
                    await asyncio.sleep(30)

        socket = [*conv.history, {"role": "user", "content": text}]
        context = LLMContext(messages=socket)
        # Pipecat's base processing needs a running pipeline; the governed turn
        # (and its barge-in handling) is entirely in this service's override.
        with patch.object(AgentIntelligence, "execute_task_streaming", _spy), patch.object(
            LLMService, "process_frame", AsyncMock()
        ):
            task = asyncio.create_task(llm.process_frame(LLMContextFrame(context=context), FrameDirection.DOWNSTREAM))
            await asyncio.wait_for((spoke if after_speech else started).wait(), timeout=60)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        llm._push_llm_text = original_push  # type: ignore[method-assign]
        spoken = " ".join(s.strip() for s in llm._scenario_spoken if s.strip())
        llm._scenario_spoken.clear()
        conv.history.append({"role": "user", "content": text})
        if after_speech and spoken:
            conv.history.append({"role": "assistant", "content": spoken})

    async def run_voice_turn(self, conv: Conversation, text: str) -> tuple[str, str, list[Any]]:
        llm = self._voice_service(conv)
        captured: dict[str, Any] = {}
        from app.operators.agent_intelligence import AgentIntelligence
        from app.operators.stream_events import AssistantStreamComplete

        original = AgentIntelligence.execute_task_streaming

        async def _spy(self_: Any, **kwargs: Any):
            captured["kwargs"] = kwargs
            async for event in original(self_, **kwargs):
                if isinstance(event, AssistantStreamComplete):
                    captured["complete"] = event
                yield event

        class _Ctx:
            def __init__(self, messages: list[dict[str, Any]]) -> None:
                self._m = messages

            def get_messages(self) -> list[dict[str, Any]]:
                return list(self._m)

        # Pipecat's context holds the live socket turns of this call.
        socket = [*conv.history, {"role": "user", "content": text}]
        with patch.object(AgentIntelligence, "execute_task_streaming", _spy):
            await llm._run_gravitre_turn(_Ctx(socket))
        complete = captured.get("complete")
        spoken = " ".join(s.strip() for s in llm._scenario_spoken if s.strip())
        llm._scenario_spoken.clear()
        full = spoken or str(getattr(complete, "full_content", "") or "").strip()
        return full, str(getattr(complete, "model", "") or ""), []
