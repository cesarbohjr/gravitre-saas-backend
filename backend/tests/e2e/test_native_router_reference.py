import asyncio
import unittest
import sys
from enum import Enum
from unittest.mock import patch
from types import SimpleNamespace
from tests.e2e.native_router_reference import ReferenceIdentity, ReferenceRouterBridge, admit_reference

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
    def setUp(self):
        class TaskType(str, Enum):
            CONTENT_GENERATION = 'content_generation'
        self.module_patch=patch.dict(sys.modules, {'app.services.model_router': SimpleNamespace(TaskType=TaskType), 'app.services.cognitive_turn_kernel': SimpleNamespace(CognitiveTurnRequest=lambda **kwargs: SimpleNamespace(**kwargs))})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)

    async def test_disabled_and_missing_identity(self):
        with self.assertRaises(PermissionError):
            ReferenceRouterBridge(RouterStub(),IDENTITY)
        with self.assertRaises(PermissionError):
            ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True)
        with self.assertRaises(PermissionError):
            ReferenceRouterBridge(RouterStub(),ReferenceIdentity("","s","u"),enabled=True,_admitted=True)
    async def test_canonical_router_invoked_without_execution_authority(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
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
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
        it=bridge.reason("first")
        self.assertEqual(await anext(it),"hello ")
        bridge.cancel()
        self.assertEqual([x async for x in it],[])
        self.assertEqual(router.cancelled,1)
    async def test_closed_and_invalid_turns(self):
        bridge=ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True,_admitted=True)
        bridge.close()
        with self.assertRaises(ValueError):
            await anext(bridge.reason("hello"))
        fresh=ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True,_admitted=True)
        with self.assertRaises(ValueError):
            await anext(fresh.reason(" "*16001))

    async def test_completed_turns_retained_across_followups(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
        self.assertEqual([x async for x in bridge.reason("What happened?")],["hello ","world"])
        self.assertEqual([x async for x in bridge.reason("Why?")],["hello ","world"])
        self.assertEqual(router.calls[1][2]["context"],[
            {"role":"user","content":"What happened?"},
            {"role":"assistant","content":"hello world"}])

    async def test_interrupted_answer_never_commits_to_context(self):
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
        it=bridge.reason("old question")
        self.assertEqual(await anext(it),"hello ")
        bridge.cancel()
        self.assertEqual([x async for x in it],[])
        self.assertEqual(bridge.history,[])
        self.assertEqual([x async for x in bridge.reason("new question")],["hello ","world"])
        self.assertEqual(router.calls[-1][2]["context"],[])

    async def test_session_isolation_and_close(self):
        router=RouterStub()
        first=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
        second=ReferenceRouterBridge(router,ReferenceIdentity("test-org","other-session","test-user"),enabled=True,_admitted=True)
        self.assertEqual([x async for x in first.reason("private")],["hello ","world"])
        self.assertEqual([x async for x in second.reason("separate")],["hello ","world"])
        self.assertEqual(router.calls[-1][2]["context"],[])
        first.close()
        self.assertTrue(first.closed)

    async def test_authenticated_scoped_admission(self):
        calls=[]
        async def lookup(org, conversation, user):
            calls.append((org,conversation,user))
            return {"id":conversation,"org_id":org,"user_id":user}
        bridge=await admit_reference(RouterStub(),IDENTITY,authenticated_user_id="test-user",
                                     lookup_conversation=lookup,enabled=True)
        self.assertEqual(calls,[("test-org","test-session","test-user")])
        self.assertEqual([x async for x in bridge.reason("Hi")],["hello ","world"])

    async def test_reject_cross_tenant_and_untrusted_principal(self):
        async def cross_tenant(org,conversation,user):
            return {"id":conversation,"org_id":"other-org","user_id":user}
        with self.assertRaises(PermissionError):
            await admit_reference(RouterStub(),IDENTITY,authenticated_user_id="test-user",
                                  lookup_conversation=cross_tenant,enabled=True)
        with self.assertRaises(PermissionError):
            await admit_reference(RouterStub(),IDENTITY,authenticated_user_id="other-user",
                                  lookup_conversation=cross_tenant,enabled=True)
        async def unavailable(*args):
            raise RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            await admit_reference(RouterStub(),IDENTITY,authenticated_user_id="test-user",
                                  lookup_conversation=unavailable,enabled=True)

    async def test_real_scoped_lookup_query_shape(self):
        from tests.e2e.native_router_reference import admit_from_authenticated_client
        class Query:
            def __init__(self):
                self.filters=[]
            def select(self,columns):
                self.columns=columns
                return self
            def eq(self,key,value):
                self.filters.append((key,value))
                return self
            def limit(self,n):
                assert n == 1
                return self
            def execute(self):
                return SimpleNamespace(data=[{"id":"test-session","org_id":"test-org","user_id":"test-user"}])
        class Client:
            def __init__(self):
                self.query=Query()
            def table(self,name):
                assert name == "conversations"
                return self.query
        client=Client()
        bridge=await admit_from_authenticated_client(
            RouterStub(),IDENTITY,authenticated_user_id="test-user",
            client=client,enabled=True)
        self.assertEqual(client.query.filters,[
            ("id","test-session"),("org_id","test-org"),("user_id","test-user")])
        self.assertEqual(bridge.identity,IDENTITY)

    async def test_scoped_lookup_rejects_missing_row(self):
        from tests.e2e.native_router_reference import admit_from_authenticated_client
        class Query:
            def select(self,*args): return self
            def eq(self,*args): return self
            def limit(self,*args): return self
            def execute(self): return SimpleNamespace(data=[])
        class Client:
            def table(self,*args): return Query()
        with self.assertRaises(PermissionError):
            await admit_from_authenticated_client(
                RouterStub(),IDENTITY,authenticated_user_id="test-user",
                client=Client(),enabled=True)

    async def test_canonical_kernel_receives_bound_full_depth_context(self):
        class Kernel:
            def __init__(self): self.requests=[]
            async def run_pre_act(self,request):
                self.requests.append(request)
                return SimpleNamespace(skipped=False,verify={"passed":True},govern={"ok":True})
        kernel=Kernel()
        bridge=ReferenceRouterBridge(RouterStub(),IDENTITY,enabled=True,_admitted=True)
        self.assertEqual([x async for x in bridge.reason("Explain this",kernel=kernel,task_state={"current_plan":"test"})],["hello ","world"])
        req=kernel.requests[0]
        self.assertEqual((req.org_id,req.user_id,req.conversation_id),("test-org","test-user","test-session"))
        self.assertEqual(req.reasoning_depth,"full")
        self.assertEqual(req.environment_name,"nonproduction")
        self.assertEqual(req.task_state,{"current_plan":"test"})

    async def test_kernel_rejection_never_starts_model(self):
        class Kernel:
            async def run_pre_act(self,request):
                return SimpleNamespace(skipped=False,verify={"passed":True},govern={"ok":False})
        router=RouterStub()
        bridge=ReferenceRouterBridge(router,IDENTITY,enabled=True,_admitted=True)
        with self.assertRaises(PermissionError):
            await anext(bridge.reason("Do it",kernel=Kernel()))
        self.assertEqual(router.calls,[])
        self.assertEqual(bridge.history,[])
