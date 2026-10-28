"""Bounded host client for a disposable pinned SDK, never an application store."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading

from contracts import Scope, mem0_search_contract


class EngineUnavailable(RuntimeError):
    pass


class Mem0Engine:
    def __init__(self, python: Path, store: Path, *, namespace_key: bytes, timeout=20):
        if not isinstance(namespace_key, bytes) or len(namespace_key) < 32:
            raise ValueError("Dedicated namespace key required")
        self.python, self.store, self.key = python, store, namespace_key
        self.timeout = timeout
        self.process = None
        self.commands = 0
        self.lock = threading.RLock()
        self.refs = {}

    def _receive(self):
        selector = selectors.DefaultSelector()
        try:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(self.timeout):
                self.process.kill()
                raise EngineUnavailable("Candidate deadline exceeded")
            line = self.process.stdout.readline(100001)
            if not line or len(line) > 100000:
                raise EngineUnavailable("Invalid candidate protocol")
            result = json.loads(line)
            if not isinstance(result, dict):
                raise EngineUnavailable("Invalid candidate protocol")
            return result
        except (ValueError, OSError):
            raise EngineUnavailable("Candidate protocol failed") from None
        finally:
            selector.close()

    def _start(self):
        if self.process is not None:
            if self.process.poll() is not None:
                raise EngineUnavailable("Candidate process stopped")
            return
        # Runtime receives no inherited provider/service credentials.
        names = {"PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR"}
        env = {k: v for k, v in os.environ.items() if k in names or k.lower().endswith("_proxy")}
        env.update({"MEM0_TELEMETRY": "false", "PYTHONUNBUFFERED": "1"})
        self.store.mkdir(parents=True, exist_ok=True)
        self.log = (self.store / "worker.log").open("a")
        try:
            self.process = subprocess.Popen([str(self.python), str(Path(__file__).with_name("sdk_worker.py")), str(self.store)],
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                            text=True, env=env, bufsize=1)
        except OSError:
            self.log.close()
            raise EngineUnavailable("Candidate interpreter failed") from None
        ready = self._receive()
        manifest = json.loads(Path(__file__).with_name("engine_source.json").read_text())
        if ready.get("ready") is not True or ready.get("version") != manifest["version"] or ready.get("files") != manifest["files"]:
            self._abort()
            raise EngineUnavailable("Candidate source verification failed")
        self.runtime_manifest = ready

    def call(self, op, scope, **kwargs):
        with self.lock:
            payload = json.dumps({"op": op, "scope": scope, **kwargs}) + "\n"
            if len(payload) > 100000:
                raise ValueError("Bounded candidate command required")
            self._start()
            self.commands += 1
            try:
                self.process.stdin.write(payload)
                self.process.stdin.flush()
                result = self._receive()
            except (EngineUnavailable, BrokenPipeError, OSError):
                self._abort()
                raise EngineUnavailable("Candidate transport failed") from None
            if result.get("ok") is not True:
                raise EngineUnavailable("Candidate operation failed")
            return result

    def scope(self, org, user, agent):
        return mem0_search_contract(Scope(org, user, agent), "synthetic", namespace_key=self.key)["filters"]

    def ref(self, scope, canonical_id):
        if not isinstance(canonical_id, str) or not 0 < len(canonical_id) <= 200:
            raise ValueError("Bounded canonical identity required")
        value = hmac.new(self.key, json.dumps([scope, canonical_id], sort_keys=True).encode(), hashlib.sha256).hexdigest()
        self.refs[value] = (scope.copy(), canonical_id)
        return value

    def upsert(self, scope, canonical_id, text):
        return self.call("upsert", scope, ref=self.ref(scope, canonical_id), text=text)

    def search(self, scope, query):
        result = self.call("search", scope, query=query)
        if not isinstance(result.get("refs"), list) or len(result["refs"]) > 8:
            raise EngineUnavailable("Invalid candidate identities")
        if any(not isinstance(ref, str) or len(ref) != 64 for ref in result["refs"]):
            raise EngineUnavailable("Invalid candidate identities")
        return list(dict.fromkeys(self.refs[ref][1] for ref in result["refs"]
                                  if ref in self.refs and self.refs[ref][0] == scope))

    def _abort(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process.stdin.close()
            self.process.stdout.close()
            self.log.close()
            self.process = None

    def close(self):
        with self.lock:
            if self.process is None:
                return {"external_attempts": 0, "inference_calls": 0}
            try:
                self.process.stdin.write('{"op":"close"}\n')
                self.process.stdin.flush()
                result = self._receive()
                if result.get("ok") is not True or result.get("external_attempts") != 0 or result.get("inference_calls") != 0:
                    raise EngineUnavailable("Candidate isolation failed")
                self.process.wait(timeout=5)
                if self.process.returncode != 0:
                    raise EngineUnavailable("Candidate shutdown failed")
                return result
            finally:
                self._abort()
