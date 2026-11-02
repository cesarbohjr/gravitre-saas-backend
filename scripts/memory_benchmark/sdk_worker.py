"""Disposable real Mem0 process. JSON protocol; no credentials, model or network IO."""
from __future__ import annotations
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
DIMENSIONS = 128


class ControlledEmbedding:
    """Fixed CPU token hashing for lifecycle comparisons, not semantic quality."""
    def __init__(self, config):
        self.config = config

    def embed(self, text, memory_action=None):
        vector = [0.0] * DIMENSIONS
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4], "big") % DIMENSIONS] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class NoInference:
    calls = 0
    def __init__(self, config):
        self.config = config

    def generate_response(self, *args, **kwargs):
        type(self).calls += 1
        raise RuntimeError("Inference is forbidden in the controlled lifecycle run")


def main():
    store = Path(sys.argv[1]).resolve()
    store.mkdir(parents=True, exist_ok=True)
    os.environ["MEM0_TELEMETRY"] = "false"
    os.environ["MEM0_DIR"] = str(store / "config")
    from tests import offline_network as guard
    guard.pytest_configure(None)
    try:
        # Explicit dependency injection only. Memory, Qdrant, SQLite and all
        # lifecycle algorithms remain upstream code. No SDK operations mocked.
        from mem0 import Memory
        from mem0.utils.factory import EmbedderFactory, LlmFactory
        from mem0.memory import telemetry
        if telemetry.MEM0_TELEMETRY:
            raise RuntimeError("Telemetry must be disabled before SDK import")
        EmbedderFactory.provider_to_class["openai"] = "sdk_worker.ControlledEmbedding"
        LlmFactory.register_provider("openai", "sdk_worker.NoInference")
        with contextlib.redirect_stdout(sys.stderr):
            memory = Memory.from_config({
                "embedder": {"provider": "openai", "config": {"embedding_dims": DIMENSIONS}},
                "llm": {"provider": "openai", "config": {"model": "forbidden-inference"}},
                "vector_store": {"provider": "qdrant", "config": {
                    "path": str(store / "vectors"), "collection_name": "controlled_memory",
                    "embedding_model_dims": DIMENSIONS}},
                "history_db_path": str(store / "history.sqlite"),
            })
        binding_path = store / "bindings.json"
        bindings = json.loads(binding_path.read_text()) if binding_path.exists() else {}

        def owned(scope, ref):
            item = bindings.get(ref)
            if not item or item["scope"] != scope:
                raise ValueError("Unknown scoped binding")
            row = memory.get(item["vendor_id"])
            if row.get("user_id") != scope["user_id"] or row.get("agent_id") != scope["agent_id"]:
                raise ValueError("Candidate ownership mismatch")
            return item["vendor_id"]

        def persist():
            temp = binding_path.with_suffix(".pending")
            temp.write_text(json.dumps(bindings))
            temp.replace(binding_path)

        import importlib.metadata
        import mem0
        package = Path(mem0.__file__).resolve().parent.parent
        manifest = json.loads(Path(__file__).with_name("engine_source.json").read_text())
        hashes = {p: hashlib.sha256((package / p).read_bytes()).hexdigest() for p in manifest["files"]}
        print(json.dumps({"ready": True, "version": importlib.metadata.version("mem0ai"), "files": hashes}), flush=True)
        for line in sys.stdin:
            try:
                if len(line) > 100000:
                    raise ValueError("Oversized command")
                command = json.loads(line)
                op = command["op"]
                if op == "close":
                    print(json.dumps({"ok": True, "external_attempts": len(guard._attempts),
                                      "inference_calls": memory.llm.calls}), flush=True)
                    break
                scope = command["scope"]
                if set(scope) != {"user_id", "agent_id"} or any(not re.fullmatch(r"[0-9a-f]{64}", str(v)) for v in scope.values()):
                    raise ValueError("Complete opaque scope required")
                ref = command.get("ref")
                if op in ("upsert", "delete", "get") and not re.fullmatch(r"[0-9a-f]{64}", str(ref)):
                    raise ValueError("Opaque canonical binding required")
                with contextlib.redirect_stdout(sys.stderr):
                    if op == "upsert":
                        text = command["text"]
                        if not isinstance(text, str) or not 0 < len(text) <= 2000:
                            raise ValueError("Bounded synthetic text required")
                        if ref in bindings:
                            memory.update(owned(scope, ref), text=text)
                        else:
                            result = memory.add(text, infer=False, **scope)
                            rows = result["results"]
                            if len(rows) != 1 or rows[0]["event"] != "ADD":
                                raise ValueError("Unexpected SDK add result")
                            bindings[ref] = {"scope": scope, "vendor_id": rows[0]["id"]}
                        persist()
                        result = {"ok": True}
                    elif op == "get":
                        row = memory.get(owned(scope, ref))
                        result = {"ok": True, "text_sha256": hashlib.sha256(row["memory"].encode()).hexdigest()}
                    elif op == "delete":
                        vendor_id = owned(scope, ref)
                        memory.delete(vendor_id)
                        if memory.get(vendor_id) is not None:
                            raise ValueError("Delete readback failed")
                        del bindings[ref]
                        persist()
                        result = {"ok": True, "history_rows_remaining": len(memory.history(vendor_id))}
                    elif op == "search":
                        query = command["query"]
                        if not isinstance(query, str) or not 0 < len(query) <= 2000:
                            raise ValueError("Bounded synthetic query required")
                        response = memory.search(query, filters=scope, top_k=8, threshold=0.0, rerank=False)
                        reverse = {v["vendor_id"]: ref for ref, v in bindings.items() if v["scope"] == scope}
                        result = {"ok": True, "refs": list(dict.fromkeys(reverse[r["id"]] for r in response["results"] if r["id"] in reverse))}
                    else:
                        raise ValueError("Unsupported operation")
                if guard._attempts:
                    raise RuntimeError("SDK attempted network IO")
                print(json.dumps(result), flush=True)
            except Exception as error:
                # No content/identity/vendor error bodies cross the protocol.
                print(json.dumps({"ok": False, "error": type(error).__name__}), flush=True)
        memory.vector_store.client.close()
        memory.close()
        if guard._attempts:
            raise RuntimeError("SDK attempted network IO")
    finally:
        guard.pytest_unconfigure(None)


if __name__ == "__main__":
    main()
