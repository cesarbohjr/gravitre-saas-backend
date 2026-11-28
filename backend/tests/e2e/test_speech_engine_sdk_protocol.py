"""Exercise the installed SDK over an actual in-process ASGI WebSocket.
No provider requests; only a synthetic key and a local TestClient.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import tempfile
import time
import unittest
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from elevenlabs.speech_engine.resource import SpeechEngineResource
from tests.e2e.speech_engine_reference import Binding, BindingStore, attach

KEY = "local-synthetic-reference-key-not-a-provider-credential"
HEADER = "x-elevenlabs-speech-engine-authorization"

def token(key=KEY):
    def enc(raw):
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")
    now = int(time.time())
    head = enc(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    body = enc(json.dumps({"iss":"https://api.elevenlabs.io/convai/speech-engine","sub":"convai_speech_engine_upstream","iat":now,"exp":now+60}).encode())
    sig = enc(hmac.new(hashlib.sha256(key.encode()).digest(),f"{head}.{body}".encode(),hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"

class ActualSdkProtocol(unittest.TestCase):
    def test_signed_init_stream_interrupt_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=BindingStore(Path(tmp)/"bindings.sqlite")
            binding=Binding("local-conversation","local-session")
            store.provision(binding)
            engine=SpeechEngineResource("local-engine",client_wrapper=SimpleNamespace(get_headers=lambda:{"xi-api-key":KEY}))
            app=FastAPI()
            cancelled=[]
            async def reason(text):
                yield text+"-first"
                if text=="old":
                    try:
                        await asyncio.sleep(60)
                    except asyncio.CancelledError:
                        cancelled.append(True)
                        raise
                yield text+"-last"
            @app.websocket("/ws")
            async def endpoint(ws:WebSocket):
                await attach(engine,ws,binding,reason,store)
            with TestClient(app) as client:
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect("/ws",headers={HEADER:token("wrong")}):
                        pass
                with client.websocket_connect("/ws",headers={HEADER:token()}) as ws:
                    ws.send_json({"type":"init","conversation_id":"local-conversation"})
                    ws.send_json({"type":"ping"})
                    self.assertEqual(ws.receive_json()["type"],"pong")
                    first_sent=time.monotonic_ns()
                    ws.send_json({"type":"user_transcript","event_id":1,"user_transcript":[{"role":"user","content":"old"}]})
                    first=ws.receive_json()
                    first_ms=(time.monotonic_ns()-first_sent)/1e6
                    self.assertEqual((first["type"],first["event_id"],first["content"]),("agent_response",1,"old-first"))
                    interrupt_sent=time.monotonic_ns()
                    ws.send_json({"type":"user_transcript","event_id":2,"user_transcript":[{"role":"user","content":"new"}]})
                    chunks=[]
                    for _ in range(10):
                        msg=ws.receive_json()
                        if not chunks:
                            second_ms=(time.monotonic_ns()-interrupt_sent)/1e6
                        self.assertEqual(msg["type"],"agent_response")
                        self.assertEqual(msg["event_id"],2)
                        chunks.append(msg["content"])
                        if msg["is_final"]:
                            break
                    self.assertTrue(msg["is_final"])
                    self.assertEqual("".join(chunks),"new-firstnew-last")
                    ws.send_json({"type":"close"})
                self.assertTrue(cancelled)
                if os.getenv('SPEECH_REFERENCE_EVIDENCE'):
                    Path(os.environ['SPEECH_REFERENCE_EVIDENCE']).write_text(json.dumps({'sourceSha':os.getenv('GITHUB_SHA'),'synthetic':True,'scope':'protocol-only','trials':[{'workloadId':'interrupt-recover-v1','repeat':1,'firstTextMs':first_ms,'secondTextMs':second_ms,'firstAudioMs':None,'interruptResidualMs':None,'completed':True,'cancelled':True}]}))
                with self.assertRaises(WebSocketDisconnect):
                    with client.websocket_connect("/ws",headers={HEADER:token()}):
                        pass
