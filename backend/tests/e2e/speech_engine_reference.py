"""Isolated Speech Engine adapter. No production route, credentials or tools.
The caller supplies an SDK resource and an independently provisioned one-use
conversation binding. Provider authentication is not tenant authorization.
"""
import asyncio
import sqlite3
import time
from dataclasses import dataclass

@dataclass(frozen=True)
class Binding:
    conversation_id: str
    session_id: str

class BindingStore:
    """Atomic, persistent, one-use reference admission. No production authority."""
    def __init__(self, path):
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS bindings (session_id TEXT PRIMARY KEY, conversation_id TEXT UNIQUE NOT NULL, expires REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)')

    def provision(self, binding, ttl=60):
        if not binding.session_id or not binding.conversation_id or not 0 < ttl <= 300:
            raise ValueError('invalid binding')
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO bindings(session_id,conversation_id,expires) VALUES(?,?,?)',(binding.session_id,binding.conversation_id,time.time()+ttl))

    def consume(self, binding):
        with sqlite3.connect(self.path) as db:
            result=db.execute('UPDATE bindings SET consumed=1 WHERE session_id=? AND conversation_id=? AND consumed=0 AND expires>?',(binding.session_id,binding.conversation_id,time.time()))
            return result.rowcount==1

class Bridge:
    def __init__(self, binding, reason):
        if not binding.conversation_id or not binding.session_id:
            raise ValueError("server binding required")
        self.binding = binding
        self.reason = reason
        self.generation = 0
        self.closed = False
        self.initialized = False
        self.active = None

    def invalidate(self):
        self.generation += 1
        if self.active and self.active is not asyncio.current_task():
            self.active.cancel()

    def init(self, conversation_id):
        if self.closed or self.initialized or conversation_id != self.binding.conversation_id:
            self.close()
            raise PermissionError("invalid conversation binding")
        self.initialized = True

    def close(self):
        self.closed = True
        self.invalidate()

    async def transcript(self, messages, session):
        if self.closed or not self.initialized or session.conversation_id != self.binding.conversation_id:
            raise PermissionError("unbound session")
        self.invalidate()
        generation = self.generation
        self.active = asyncio.current_task()
        # Only latest user text; provider-supplied history is not authority.
        try:
            if not messages or messages[-1].role != "user":
                raise ValueError("missing user turn")
            text = messages[-1].content
            if not isinstance(text, str) or not text.strip() or len(text)>16000:
                raise ValueError("invalid transcript")
            async def stream():
                async for chunk in self.reason(text):
                    if self.closed or generation != self.generation:
                        return
                    if not isinstance(chunk, str):
                        raise TypeError("invalid response chunk")
                    yield chunk
            await session.send_response(stream())
        finally:
            if self.active is asyncio.current_task():
                self.active = None

async def attach(engine, websocket, binding, reason, store=None):
    # SDK validates provider JWT before any upgrade; no bypass switch.
    if not engine.verify_request(dict(websocket.headers)):
        await websocket.close(code=1008)
        return
    if store is None or not store.consume(binding):
        await websocket.close(code=1008)
        return
    bridge = Bridge(binding, reason)
    await websocket.accept()
    session = engine.create_session(websocket, debug=False)
    session.on("init", bridge.init)
    async def on_transcript(messages):
        await bridge.transcript(messages, session)
    session.on("user_transcript", on_transcript)
    session.on("close", bridge.close)
    session.on("disconnected", bridge.close)
    session.on("error", lambda error: bridge.close())
    try:
        await session.run()
    finally:
        bridge.close()

async def tool_free_reason(text):
    # Deliberately deterministic, no network calls or business effects.
    yield "I received your message. "
    yield "This is an isolated conversational reference."
