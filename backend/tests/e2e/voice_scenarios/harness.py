"""Drive the production Pipecat voice pipeline through one scripted conversation.

``run_scenario`` builds the real pipeline with ``build_pipecat_voice_task`` (the
same call the router makes), swaps only the providers, the client and the data
stores, plays the scenario's user timeline on a virtual clock and returns a
``RunResult`` with everything the metrics need.

The patches (``bench_patches``) are installed for the duration of one run and
restored afterwards; they point at whichever run is current, so runs are
sequential.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import random
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

# Settings must load, but nothing may reach a real service.
for _key, _value in {
    "APP_ENV": "dev",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
    "SUPABASE_JWT_SECRET": "jwt-secret-test",
    "OPENAI_API_KEY": "sk-test-openai",
    "AI_MODERATION_ENABLED": "false",
    "GRAVITRE_DROP_BACKGROUND_TASKS": "1",
}.items():
    if not os.environ.get(_key):
        os.environ[_key] = _value

from tests.e2e.voice_scenarios.fakes import (  # noqa: E402
    SPEC_RUN,
    BenchSupabase,
    BrowserPlaybackModel,
    FakeClientWebSocket,
    FakeStreamingTTS,
    Planner,
    Recorder,
    ScriptedBrain,
    ScriptedFluxSTT,
    TTSConditions,
    install_created_at_hook,
    norm_words,
)
from tests.e2e.voice_scenarios.virtual_clock import VirtualClock, run_virtual  # noqa: E402

ORG_ID = "00000000-0000-4000-8000-0000000000b1"
USER_ID = "00000000-0000-4000-8000-0000000000c4"


@dataclass
class Conditions:
    """Scripted delays (seconds). Each draw is jittered by +/- ``jitter``."""

    brain_first_token_s: float = 0.9
    token_s: float = 0.035
    tts_first_byte_s: float = 0.25
    tts_generation_speed: float = 3.0
    tts_word_audio_s: float = 0.32
    late_audio_s: float = 0.0
    user_word_s: float = 0.3
    stt_start_detect_s: float = 0.15
    stt_eager_delay_s: float = 0.2
    stt_eot_delay_s: float = 0.45
    browser_lead_s: float = 0.12
    network_s: float = 0.0
    jitter: float = 0.25
    stt_interims: bool = False

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Utterance:
    text: str
    role: str
    start: float
    end: float | None = None  # acoustic end of speech
    final_at: float | None = None
    finals: list[str] = field(default_factory=list)


class _Socket:
    """One browser socket and the pipeline serving it."""

    def __init__(self, run: "Run", index: int) -> None:
        self.run = run
        self.index = index
        self.browser = BrowserPlaybackModel(run.rec, initial_lead_s=run.cond.browser_lead_s, network_s=run.cond.network_s)
        self.ws = FakeClientWebSocket(run.rec, self.browser)
        self.stt = ScriptedFluxSTT(recorder=run.rec, emit_interims=run.cond.stt_interims)
        self.tts = FakeStreamingTTS(
            recorder=run.rec,
            conditions=TTSConditions(
                first_byte_s=run.cond.tts_first_byte_s,
                word_audio_s=run.cond.tts_word_audio_s,
                generation_speed=run.cond.tts_generation_speed,
                late_audio_s=run.cond.late_audio_s,
            ),
            rng=run.rng,
        )
        self.task: Any = None
        self.runner_task: asyncio.Task[Any] | None = None
        self.meta: dict[str, Any] = {}

    async def open(self) -> None:
        from pipecat.pipeline.runner import PipelineRunner

        from app.services.pipecat_voice.pipeline import build_pipecat_voice_task
        from app.services.pipecat_voice.stt_factory import STT_FLUX

        self.task, self.meta = build_pipecat_voice_task(
            websocket=self.ws,
            settings=self.run.settings,
            org_id=ORG_ID,
            user_id=USER_ID,
            conversation_id=self.run.conversation_id,
            stt_service=self.stt,
            stt_service_info={"stt_provider_key": STT_FLUX, "stt_provider": "bench_scripted_flux"},
            tts_service=self.tts,
        )
        reporter = getattr(self.task, "gravitre_interrupt_reporter", None)
        session = getattr(reporter, "_voice_session", None)
        self.run.rec.voice_session = session
        self.runner_task = asyncio.get_running_loop().create_task(PipelineRunner(handle_sigint=False).run(self.task))
        await asyncio.wait_for(self.ws.ready.wait(), timeout=10)
        self.run.rec.log("socket_open", index=self.index)

    async def close(self) -> None:
        if self.task is not None:
            try:
                await self.task.cancel()
            except Exception:  # noqa: BLE001
                pass
        if self.runner_task is not None:
            try:
                await asyncio.wait_for(self.runner_task, timeout=5)
            except BaseException:  # noqa: BLE001
                pass
        reporter = getattr(self.task, "gravitre_interrupt_reporter", None)
        if reporter is not None:
            try:
                await reporter.release_stop_marker()
            except Exception:  # noqa: BLE001
                pass


class Run:
    """One scenario run: the user's side of the conversation plus observation."""

    def __init__(self, *, scenario: Any, seed: int, conditions: Conditions, settings: Any, clock: VirtualClock) -> None:
        self.scenario = scenario
        self.seed = seed
        self.cond = conditions
        self.settings = settings
        self.clock = clock
        self.rng = random.Random(seed)
        self.rec = Recorder(clock)
        self.db = BenchSupabase(clock)
        install_created_at_hook(self.db)
        self.conversation_id = self.db.seed_conversation(org_id=ORG_ID, user_id=USER_ID)
        for i, (role, content) in enumerate(getattr(scenario, "seed_history", []) or []):
            self.db.tables.setdefault("conversation_messages", []).append(
                {
                    "id": f"seed-{i}",
                    "conversation_id": self.conversation_id,
                    "role": role,
                    "content": content,
                    "created_at": f"2026-10-05T10:00:{i:02d}Z",
                }
            )
        self.seed_rows = len(self.db.tables.get("conversation_messages", []))
        self.brain = ScriptedBrain(self.rec, scenario.planner, self, settings=settings, org_id=ORG_ID)
        self.utterances: list[Utterance] = []
        self.sockets: list[_Socket] = []
        self.marks: dict[str, float] = {}
        # VoicePipelineSession.reply_id at each mark: replies after it answer
        # what was said after the mark.
        self.mark_replies: dict[str, int] = {}
        self.notes: dict[str, Any] = {}

    # -- helpers ------------------------------------------------------------

    def jit(self, base: float) -> float:
        return max(0.0, base * (1.0 + self.rng.uniform(-self.cond.jitter, self.cond.jitter)))

    @property
    def now(self) -> float:
        return self.clock.now

    @property
    def socket(self) -> _Socket:
        return self.sockets[-1]

    def reply_id(self) -> int:
        return int(getattr(self.rec.voice_session, "reply_id", 0) or 0)

    def mark(self, name: str) -> None:
        self.marks[name] = self.now
        self.mark_replies[name] = self.reply_id()
        self.rec.log("mark", name=name, reply_id=self.mark_replies[name])

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds))

    async def wait_for(self, predicate: Callable[[], bool], timeout: float = 15.0, step: float = 0.02) -> bool:
        deadline = self.now + timeout
        while self.now < deadline:
            if predicate():
                return True
            await asyncio.sleep(step)
        return predicate()

    def audio_received(self, label: str | None = None, since: float = 0.0) -> bool:
        for t, _seg, lab in self._audio_arrivals():
            if t >= since and (label is None or lab == label):
                return True
        return False

    def audio_playing(self, label: str | None = None) -> bool:
        now = self.now
        for c in self.socket.browser.chunks:
            if c["start"] <= now < c["played_end"] and (label is None or c["label"] == label):
                return True
        return False

    def _audio_arrivals(self) -> list[tuple[float, int, str]]:
        out = []
        for c in self.socket.browser.chunks + self.socket.browser.dropped:
            out.append((c["recv"], c["seg"], c["label"]))
        return out

    def brain_idle(self) -> bool:
        return all(c.ended_at is not None for c in self.rec.brain_calls if not c.speculative or c.spec_run.get("adopted"))

    def playback_idle(self) -> bool:
        now = self.now
        return all(c["played_end"] <= now for c in self.socket.browser.chunks)

    async def open_socket(self) -> _Socket:
        sock = _Socket(self, len(self.sockets))
        self.sockets.append(sock)
        await sock.open()
        return sock

    async def drop_socket(self) -> None:
        """Network drop: the client socket disappears mid-session."""
        self.rec.log("socket_drop", index=self.socket.index)
        self.socket.ws.drop()

    # -- the user's voice ---------------------------------------------------

    async def say(
        self,
        text: str,
        *,
        role: str = "request",
        pauses: dict[int, float] | None = None,
        commit_on_pause: bool = False,
        eot_delay_s: float | None = None,
        mark_start: str | None = None,
        mark_end: str | None = None,
    ) -> Utterance:
        """Speak ``text`` now. ``pauses`` maps word index -> silence after that word.

        Flux behaviour modelled: StartOfTurn ``stt_start_detect_s`` after speech
        starts; during a pause longer than the eager delay an EagerEndOfTurn is
        emitted and withdrawn (TurnResumed) when speech resumes; with
        ``commit_on_pause`` a pause longer than the EOT delay commits the turn
        early and the rest of the speech opens a new turn. EndOfTurn (final
        transcript + ProposedUserStopped) lands ``stt_eot_delay_s`` after the
        speech ends.
        """
        words = text.split()
        pauses = pauses or {}
        utt = Utterance(text=text, role=role, start=self.now)
        if mark_start:
            self.mark(mark_start)
        self.utterances.append(utt)
        self.rec.log("user_speech_start", text=text, role=role)
        stt = self.socket.stt
        detect = self.jit(self.cond.stt_start_detect_s)
        eager_d = self.jit(self.cond.stt_eager_delay_s)
        eot_d = self.jit(eot_delay_s if eot_delay_s is not None else self.cond.stt_eot_delay_s)
        turn_open_at = self.now + detect
        turn_open = False
        segment_words: list[str] = []
        for i, word in enumerate(words):
            word_end = self.now + self.jit(self.cond.user_word_s)
            if not turn_open and turn_open_at <= word_end:
                await self.sleep(turn_open_at - self.now)
                await stt.start_of_turn()
                turn_open = True
            await self.sleep(word_end - self.now)
            segment_words.append(word)
            await stt.update(" ".join(segment_words))
            pause = pauses.get(i)
            if pause and i < len(words) - 1:
                pause_start = self.now
                if pause > eager_d:
                    await self.sleep(eager_d)
                    await stt.eager_end_of_turn(" ".join(segment_words))
                if commit_on_pause and pause > eot_d:
                    await self.sleep(pause_start + eot_d - self.now)
                    part = " ".join(segment_words)
                    utt.finals.append(part)
                    await stt.end_of_turn(part)
                    segment_words = []
                    turn_open = False
                    await self.sleep(pause_start + pause - self.now)
                    turn_open_at = self.now + self.jit(self.cond.stt_start_detect_s)
                else:
                    await self.sleep(pause_start + pause - self.now)
                    await stt.turn_resumed()
        if not turn_open:
            await self.sleep(max(0.0, turn_open_at - self.now))
            await stt.start_of_turn()
        utt.end = self.now
        if mark_end:
            self.mark(mark_end)
        self.rec.log("user_speech_end", text=text, role=role)
        if eager_d < eot_d:
            await self.sleep(eager_d)
            await stt.eager_end_of_turn(" ".join(segment_words))
        await self.sleep(utt.end + eot_d - self.now)
        part = " ".join(segment_words)
        utt.finals.append(part)
        await stt.end_of_turn(part)
        utt.final_at = self.now
        return utt

    def say_later(self, delay: float, text: str, **kwargs: Any) -> asyncio.Task[Utterance]:
        async def _go() -> Utterance:
            await self.sleep(delay)
            return await self.say(text, **kwargs)

        return asyncio.get_running_loop().create_task(_go())

    async def settle(self, *, quiet_s: float = 1.5, max_s: float = 30.0) -> None:
        """Wait until the brain, TTS and browser playback have all gone quiet."""
        deadline = self.now + max_s
        quiet_since: float | None = None
        last_events = -1
        while self.now < deadline:
            busy = not self.brain_idle() or not self.playback_idle()
            n = len(self.rec.events) + len(self.socket.ws.sent)
            if busy or n != last_events:
                quiet_since = None
                last_events = n
            elif quiet_since is None:
                quiet_since = self.now
            elif self.now - quiet_since >= quiet_s:
                return
            await asyncio.sleep(0.05)
        self.notes["settle_timeout"] = True


# ---------------------------------------------------------------------------
# Process-wide patches


_CURRENT: dict[str, Run | None] = {"run": None}


def _current() -> Run:
    run = _CURRENT["run"]
    if run is None:
        raise RuntimeError("no bench run active")
    return run


@contextlib.contextmanager
def bench_patches() -> Iterator[None]:
    """Swap the data stores, the brain and the network for the duration of a run.

    Everything is restored on exit, so the bench can share a pytest session
    with unrelated tests.
    """
    import app.core.db as core_db
    import app.operators.agent_intelligence as agent_intelligence
    import app.routers.assistant as assistant_router
    import app.workflows.repository as repository
    from app.services import chat_turn_cancel_service
    from app.services.pipecat_voice import cognitive_llm, speculative_generation, speculative_prefetch

    saved: list[tuple[Any, str, Any]] = []

    def _set(obj: Any, name: str, value: Any) -> None:
        saved.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    def _during_run(obj: Any, name: str, bench_fn: Callable[..., Any]) -> None:
        # Modules first imported during a run may bind the replacement by name
        # (``from x import get_supabase_client``) and keep it after restore, so
        # every replacement defers to the original whenever no run is active.
        original = getattr(obj, name)

        def replacement(*args: Any, **kwargs: Any) -> Any:
            if _CURRENT["run"] is None:
                return original(*args, **kwargs)
            return bench_fn(*args, **kwargs)

        _set(obj, name, replacement)

    _during_run(repository, "get_supabase_client", lambda _settings=None: _current().db)
    _during_run(assistant_router, "get_supabase_client", lambda _settings=None: _current().db)
    _during_run(core_db, "shared_service_client", lambda *_a, **_k: _current().db)
    _during_run(assistant_router, "_remember_completed_turn", lambda **_kwargs: None)
    _during_run(chat_turn_cancel_service, "get_redis_client", lambda _settings=None: None)
    _during_run(agent_intelligence, "get_agent_intelligence", lambda: _current().brain)

    # Tag spoken narration by source so audio can be labelled at the client.
    def _tagging(fn: Any, label: str) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            out = fn(*args, **kwargs)
            run = _CURRENT["run"]
            if run is not None:
                run.rec.register_narration(out, label)
            return out

        return wrapper

    _set(cognitive_llm, "pick_deep_acknowledgement", _tagging(cognitive_llm.pick_deep_acknowledgement, "filler"))
    for name in ("narrate_tool_started", "narrate_tool_still_running", "narrate_tool_completed"):
        _set(cognitive_llm, name, _tagging(getattr(cognitive_llm, name), "progress"))

    # Speculative bookkeeping: mark the brain calls a speculative run makes,
    # and whether the confirmed turn adopted the run.
    real_start = speculative_prefetch.start_speculative_run

    def _start(*, text: str, runner: Any, create_task: Any, **kwargs: Any) -> Any:
        # **kwargs: bounds/revision added by the production signature; passed through.
        if _CURRENT["run"] is None:
            return real_start(text=text, runner=runner, create_task=create_task, **kwargs)
        rec = _current().rec
        info: dict[str, Any] = {"text": text, "started_at": rec.now(), "adopted": False, "call": None}
        rec.spec_runs.append(info)
        rec.log("spec_start", text=text)

        def _wrapped() -> Any:
            SPEC_RUN.set(info)
            return runner()

        run = real_start(text=text, runner=_wrapped, create_task=create_task, **kwargs)
        run.bench_info = info
        return run

    _set(speculative_prefetch, "start_speculative_run", _start)

    real_adopt = speculative_generation.SpeculativeGenerationCoordinator.adopt

    def _adopt(self: Any, final_text: str, **kwargs: Any) -> Any:
        run = real_adopt(self, final_text, **kwargs)
        if run is not None and getattr(run, "bench_info", None) is not None and _CURRENT["run"] is not None:
            run.bench_info["adopted"] = True
            _current().rec.log("spec_adopted", text=final_text)
        return run

    _set(speculative_generation.SpeculativeGenerationCoordinator, "adopt", _adopt)

    # Read-only cache warming calls embeddings/knowledge services over the
    # network; it has no effect on scripted answers, so it is counted only.
    real_prefetch = speculative_prefetch.SpeculativePrefetchProcessor._prefetch

    async def _prefetch(self: Any, text: str) -> None:
        run = _CURRENT["run"]
        if run is None:
            await real_prefetch(self, text)
            return
        run.rec.log("prefetch", text=text)

    _set(speculative_prefetch.SpeculativePrefetchProcessor, "_prefetch", _prefetch)

    # Anything else that tries the network fails fast instead of hanging.
    real_connect = socket.socket.connect

    def _guarded_connect(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in {"127.0.0.1", "localhost", "::1"} and self.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError(f"voice bench: outbound network disabled ({host})")
        return real_connect(self, address)

    _set(socket.socket, "connect", _guarded_connect)
    try:
        yield
    finally:
        for obj, name, value in reversed(saved):
            setattr(obj, name, value)


def build_settings(overrides: dict[str, str] | None = None) -> Any:
    from app.config import get_settings

    for key, value in (overrides or {}).items():
        os.environ[key.upper()] = str(value)
    get_settings.cache_clear()
    return get_settings()


@dataclass
class RunResult:
    scenario_id: str
    seed: int
    run: Run
    error: str | None = None


def run_scenario(scenario: Any, seed: int, *, conditions: Conditions | None = None, settings: Any = None) -> RunResult:
    """Run one scenario once on its own virtual-time loop."""
    from app.services.chat_turn_cancel_service import reset_local_stops_for_tests

    reset_local_stops_for_tests()
    cond = conditions or scenario.conditions()
    clock = VirtualClock()
    run = Run(scenario=scenario, seed=seed, conditions=cond, settings=settings or build_settings(), clock=clock)
    _CURRENT["run"] = run
    error: str | None = None

    async def _main() -> None:
        # Production code draws from the global RNG (e.g. which acknowledgement
        # to say); seed it so a run is reproducible.
        random.seed(seed)
        await run.open_socket()
        await asyncio.sleep(0.5)  # session.ready, warm-up
        run.mark("t0")
        try:
            await asyncio.wait_for(scenario.script(run), timeout=scenario.max_seconds)
            await run.settle()
        finally:
            for sock in run.sockets:
                await sock.close()

    try:
        with bench_patches():
            run_virtual(_main, clock=clock)
    except Exception as exc:  # noqa: BLE001 - one broken run must not stop the bench
        error = f"{exc.__class__.__name__}: {exc}"[:400]
    finally:
        _CURRENT["run"] = None
        reset_local_stops_for_tests()
    return RunResult(scenario_id=scenario.id, seed=seed, run=run, error=error)


__all__ = ["Conditions", "Run", "RunResult", "Utterance", "build_settings", "run_scenario", "norm_words", "ORG_ID", "USER_ID"]
