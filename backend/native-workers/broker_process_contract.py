"""Certification-only process boundaries; no production transport or permissions."""
from __future__ import annotations
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _fixture(pipe, path, page):
    lock=threading.Lock()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE writes (id INTEGER PRIMARY KEY)')
    mutated=False
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            if self.path=='/redirect':
                self.send_response(302);self.send_header('Location','/page');self.end_headers();return
            if self.path=='/page':data,kind=page,'text/html'
            elif self.path=='/state':data,kind=json.dumps({'mutated':mutated}).encode(),'application/json'
            else:self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if self.path!='/write':self.send_error(404);return
            # Only this independent server owns the committed write counter.
            with lock, sqlite3.connect(path) as db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('INSERT INTO writes DEFAULT VALUES')
            self.send_response(204);self.end_headers()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    pipe.send({'port':server.server_port,'pid':os.getpid()})
    try:
        while True:
            command,value=pipe.recv()
            if command=='close':break
            if command=='mutate':mutated=value;pipe.send(True)
            elif command=='count':
                with lock, sqlite3.connect(path) as db:
                    pipe.send(db.execute('SELECT COUNT(*) FROM writes').fetchone()[0])
            else:raise ValueError('Unknown fixture operation')
    finally:server.shutdown();server.server_close();thread.join(timeout=3);pipe.close()


class IndependentFixture:
    def __init__(self,path,page):
        context=mp.get_context('spawn');self.pipe,child=context.Pipe()
        self.process=context.Process(target=_fixture,args=(child,str(path),page))
        self.process.start();child.close()
        ready=self._receive();self.pid=ready['pid'];self.origin='http://127.0.0.1:'+str(ready['port'])
        assert self.pid!=os.getpid()
    def _receive(self):
        if not self.pipe.poll(10):raise TimeoutError('Independent fixture unavailable')
        return self.pipe.recv()
    @property
    def writes(self):self.pipe.send(('count',None));return self._receive()
    @property
    def mutated(self):return self._mutated if hasattr(self,'_mutated') else False
    @mutated.setter
    def mutated(self,value):
        self.pipe.send(('mutate',bool(value)));assert self._receive() is True;self._mutated=bool(value)
    def close(self):
        if self.process.is_alive():self.pipe.send(('close',None))
        self.process.join(timeout=5)
        if self.process.is_alive():self.process.kill();self.process.join(timeout=3)
        self.pipe.close()
        assert self.process.exitcode==0


def _broker(pipe,path,key,recover):
    from app.services.native_agent_adapters import AdapterScope
    from app.services.native_runtime.store import Journal
    journal=Journal(path,key);scope=AdapterScope('fixture-org','fixture-agent','fixture-run')
    payload={'task':{'task':'isolated fixture','allowed_hosts':[]}}
    job_id=journal.enqueue(scope,'browser_use','one-intent',payload,ttl=600,max_attempts=1)
    active=journal.claim('browser_use',lease_seconds=1)
    if recover:
        pipe.send({'pid':os.getpid(),'job_id':job_id,'claimed':active is not None,
                   'state':journal.get(scope,job_id)['state'],'action_count':len(journal.actions(scope,job_id))})
    else:
        assert active and active['id']==job_id
        pipe.send({'pid':os.getpid(),'job_id':job_id})
    try:
        while True:
            command,value=pipe.recv()
            if command=='close':break
            if command=='approve':
                request=journal.request_action(active,0,value)
                journal.approve(scope,job_id,request['id'],request['digest'],True)
                pipe.send(journal.request_action(active,0,value))
            elif command=='active':pipe.send(active is not None and journal.active(active))
            elif command=='replay':
                assert journal.enqueue(scope,'browser_use','one-intent',payload,ttl=600,max_attempts=1)==job_id
                pipe.send({'claimed':journal.claim('browser_use') is not None,
                           'action_count':len(journal.actions(scope,job_id))})
            else:raise ValueError('Unknown broker operation')
    finally:pipe.close()


class CrashBroker:
    """Real OS child broker, encrypted journal, SIGKILL and a new PID."""
    def __init__(self,root):
        from cryptography.fernet import Fernet
        Path(root).mkdir(mode=0o700)
        self.path=str(Path(root)/'journal.sqlite3');self.key=Fernet.generate_key();self.process=None
        try:self._start(False)
        except BaseException:
            if self.process and self.process.is_alive():self.process.kill();self.process.join(timeout=3)
            raise
        self.initial=self.ready
    def _start(self,recover):
        context=mp.get_context('spawn');self.pipe,child=context.Pipe()
        self.process=context.Process(target=_broker,args=(child,self.path,self.key,recover))
        self.process.start();child.close();self.ready=self._receive()
    def _receive(self):
        if not self.pipe.poll(10):raise TimeoutError('Certification broker unavailable')
        return self.pipe.recv()
    def approve(self,action):self.pipe.send(('approve',action));return self._receive()
    def authorized(self):self.pipe.send(('active',None));return self._receive()
    def kill_and_restart(self):
        old_pid=self.process.pid;os.kill(old_pid,signal.SIGKILL);self.process.join(timeout=5)
        assert self.process.exitcode==-signal.SIGKILL
        self.pipe.close()
        # Expire the actual lease using wall time, not a synthetic claim clock.
        time.sleep(1.1)
        self._start(True)
        assert self.ready['pid']!=old_pid and self.ready['job_id']==self.initial['job_id']
        assert self.ready['state']=='uncertain' and not self.ready['claimed'] and self.ready['action_count']==1
        self.pipe.send(('replay',None));replay=self._receive()
        assert replay=={'claimed':False,'action_count':1}
        return {'broker_sigkill':True,'new_broker_pid':True,'journal_state':'uncertain',
                'replayed_claims':0,'persisted_action_count':1}
    def close(self):
        if self.process and self.process.is_alive():self.pipe.send(('close',None))
        if self.process:self.process.join(timeout=5)
        if self.process and self.process.is_alive():self.process.kill();self.process.join(timeout=3)
        self.pipe.close()
