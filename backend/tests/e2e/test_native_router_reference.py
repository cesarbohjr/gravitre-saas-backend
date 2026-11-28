import asyncio
import unittest
from types import SimpleNamespace
from tests.e2e.native_router_reference import ReferenceIdentity, ReferenceRouterBridge

IDENTITY=ReferenceIdentity(org_id="test-org",session_id="test-session",user_id="test-user")

class RouterStub:
    def __init__(self):
        self.calls=[]
        self.cancelled=0
        self.events=["hello ","world"]
    async def prepare_stream(self,task,prompt,**kwargs):
        self.calls.append((task,prompt,kwargs))
        return SimpleNamespace()
    async def stream(self,prepared):
        try:
            for chunk in self.events:
                await asyncio.sleep(0)
                yield SimpleNamespace(delta=chunk)
        finally:
            self.cancelled+=1

class RouterBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_and_missing_identity(self):
        with self.assertRaises(PermissionError):
            ReferenceRouterBridge(RouterStub(),IDENTITY)
        with self.assertRaises(PermissionError):
            ReferenceRouterBridge(RouterStub(),ReferenceIdentity("","s","u"),enabled=True)
    async def test_canonical_router_invoked_without_execution_authority(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True)
        chunks=[chunk async for chunk in bridge.reason("Hello")]
        self.assertEqual(chunks,["hello ","world"])
        self.assertEqual(len(router.calls),1)
        task,prompt,kw=router.calls[0]
        self.assertEqual(task.value,"content_generation")
        self.assertEqual(kw["org_id"],"test-org")
        self.assertIs(kw["autonomous_run"],False)
        self.assertEqual(kw["context"],[])
        self.assertIn("no tools",kw["system_prompt"])
        self.assertEqual(router.cancelled,1)
    async def test_cancel_fences_late_tokens(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True)
        it=bridge.reason("first")
        self.assertEqual(await anext(it),"hello ")
        bridge.cancel()
        self.assertEqual([x async for x in it],[])
        self.assertEqual(router.cancelled,1)
    async def test_closed_and_invalid_turns(self):
        bridge=ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True)
        bridge.close()
        with self.assertRaises(ValueError):
            await anext(bridge.reason("hello"))
        fresh=ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True)
        with self.assertRaises(ValueError):
            await anext(fresh.reason(" "*16001))

    async def test_completed_turns_retained_across_followups(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True)
        self.assertEqual([x async for x in bridge.reason("What happened?")],["hello ","world"])
        self.assertEqual([x async for x in bridge.reason("Why?")],["hello ","world"])
        self.assertEqual(router.calls[1][2]["context"],[
            {"role":"user","content":"What happened?"},
            {"role":"assistant","content":"hello world"}])

    async def test_interrupted_answer_never_commits_to_context(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True)
        it=bridge.reason("old question")
        self.assertEqual(await anext(it),"hello ")
        bridge.cancel()
        self.assertEqual([x async for x in it],[])
        self.assertEqual(bridge.history,[])
        self.assertEqual([x async for x in bridge.reason("new question")],["hello ","world"])
        self.assertEqual(router.calls[-1][2]["context"],[])

    async def test_session_isolation_and_close(self):
        router=RouterStub()
        first=ReferenceRouterBridge(router,IDENTITY,enabled=True)
        second=ReferenceRouterBridge(router,ReferenceIdentity("test-org","other-session","test-user"),enabled=True)
        self.assertEqual([x async for x in first.reason("private")],["hello ","world"])
        self.assertEqual([x async for x in second.reason("separate")],["hello ","world"])
        self.assertEqual(router.calls[-1][2]["context"],[])
        first.close()
        self.assertTrue(first.closed)
