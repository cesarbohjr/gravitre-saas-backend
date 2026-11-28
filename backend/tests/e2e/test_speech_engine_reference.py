import asyncio
import unittest
import tempfile
import concurrent.futures
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from tests.e2e.speech_engine_reference import Binding, Bridge, attach, BindingStore

class Session:
    def __init__(self, cid):
        self.conversation_id=cid
        self.chunks=[]
    async def send_response(self, stream):
        async for chunk in stream:
            self.chunks.append(chunk)

def message(text):
    return [SimpleNamespace(role="user",content=text)]

class BridgeTest(unittest.IsolatedAsyncioTestCase):
    async def test_auth_rejects_before_upgrade(self):
        engine=Mock()
        engine.verify_request.return_value=False
        ws=SimpleNamespace(headers={},close=AsyncMock(),accept=AsyncMock())
        await attach(engine,ws,Binding("a","session"),None)
        ws.close.assert_awaited_once_with(code=1008)
        ws.accept.assert_not_awaited()
        engine.create_session.assert_not_called()

    async def test_session_isolation(self):
        async def reason(text):
            yield text
        bridge=Bridge(Binding("a","session"),reason)
        bridge.init("a")
        with self.assertRaises(PermissionError):
            await bridge.transcript(message("x"),Session("b"))
        with self.assertRaises(PermissionError):
            bridge.init("a")
        self.assertTrue(bridge.closed)

    async def test_stale_generation_and_cancellation(self):
        started=asyncio.Event()
        cancelled=asyncio.Event()
        async def reason(text):
            yield text
            if text=="old":
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    # Even a cancellation-resistant producer cannot emit.
                    yield "stale"
        b=Bridge(Binding("a","session"),reason)
        b.init("a")
        s=Session("a")
        old=asyncio.create_task(b.transcript(message("old"),s))
        await started.wait()
        await b.transcript(message("new"),s)
        await old
        self.assertTrue(cancelled.is_set())
        self.assertEqual(s.chunks,["old","new"])

    async def test_disconnect_and_fresh_binding(self):
        started=asyncio.Event()
        async def reason(text):
            yield text
            if text=="old":
                started.set()
                await asyncio.Event().wait()
        b=Bridge(Binding("a","session"),reason)
        b.init("a")
        s=Session("a")
        task=asyncio.create_task(b.transcript(message("old"),s))
        await started.wait()
        b.close()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with self.assertRaises(PermissionError):
            await b.transcript(message("new"),s)
        fresh=Bridge(Binding("b","fresh"),reason)
        fresh.init("b")
        s2=Session("b")
        await fresh.transcript(message("new"),s2)
        self.assertEqual(s2.chunks,["new"])

    async def test_single_use_binding_persists_and_rejects_races(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bindings.sqlite"
            store=BindingStore(path)
            binding=Binding("conversation","session")
            store.provision(binding)
            self.assertFalse(store.consume(Binding("other","session")))
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                results=list(pool.map(lambda _: BindingStore(path).consume(binding),range(8)))
            self.assertEqual(sum(results),1)
            self.assertFalse(BindingStore(path).consume(binding))

    async def test_authenticated_replay_rejected_before_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=BindingStore(Path(tmp)/"bindings.sqlite")
            binding=Binding("a","session")
            store.provision(binding)
            self.assertTrue(store.consume(binding))
            engine=Mock()
            engine.verify_request.return_value=True
            ws=SimpleNamespace(headers={},close=AsyncMock(),accept=AsyncMock())
            await attach(engine,ws,binding,None,store)
            ws.close.assert_awaited_once_with(code=1008)
            ws.accept.assert_not_awaited()
