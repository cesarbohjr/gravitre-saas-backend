"""Execute the pinned Mem0 SDK with controlled embeddings through real host gates."""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(HERE))
from sdk_client import Mem0Engine, EngineUnavailable


class KernelBackend:
    """Synthetic fixture indexing; authorization remains in the real kernel."""
    def __init__(self, engine):
        self.engine = engine

    async def recall(self, request, rows):
        # Existing rows are the synthetic candidate corpus, including stale or
        # poisoned records. Only final authoritative host checks grant recall.
        for row in rows:
            scope = self.engine.scope(row["org_id"], row.get("created_by") or request.user_id,
                                      row.get("agent_id") or request.agent_id)
            await asyncio.to_thread(self.engine.upsert, scope, row["id"], row["content"])
        scope = self.engine.scope(request.org_id, request.user_id, request.agent_id)
        ids = await asyncio.to_thread(self.engine.search, scope, request.message)
        return {"episodic_memories": [{"id": rid} for rid in ids], "graph_context": []}

    async def learn(self, request, rows):
        # Called only with rows actually written by canonical LEARN. Never
        # forwards raw extraction candidates or asks Mem0 to infer new facts.
        scope = self.engine.scope(request.org_id, request.user_id, request.agent_id)
        for row in rows:
            await asyncio.to_thread(self.engine.upsert, scope, row["id"], row["content"])
            result = await asyncio.to_thread(self.engine.call, "get", scope, ref=self.engine.ref(scope, row["id"]))
            if result["text_sha256"] != hashlib.sha256(row["content"].encode()).hexdigest():
                raise EngineUnavailable("Learn readback mismatch")
        return len(rows)


def lifecycle(python, root):
    key = b"synthetic-lifecycle-namespace-key"
    store = root / "lifecycle"
    engine = Mem0Engine(python, store, namespace_key=key)
    checks = []
    retained = None
    try:
        own = engine.scope("org-a", "user-a", "agent-a")
        others = [engine.scope("org-b", "user-a", "agent-a"),
                  engine.scope("org-a", "user-b", "agent-a"),
                  engine.scope("org-a", "user-a", "agent-b")]
        engine.upsert(own, "record-a", "synthetic preferred format concise")
        for i, scope in enumerate(others):
            engine.upsert(scope, f"foreign-{i}", "synthetic preferred format concise")
        checks.append({"id": "sdk_scope_filters", "passed": engine.search(own, "synthetic preferred format") == ["record-a"]})
        for i, scope in enumerate(others):
            for op in ("get", "upsert", "delete"):
                try:
                    kwargs = {"text": "synthetic unauthorized correction"} if op == "upsert" else {}
                    engine.call(op, scope, ref=engine.ref(own, "record-a"), **kwargs)
                except EngineUnavailable:
                    denied = True
                else:
                    denied = False
                checks.append({"id": f"sdk_foreign_{op}_denied_{i}", "passed": denied})
        try:
            engine.call("get", own, ref=engine.ref(own, "unknown"))
        except EngineUnavailable:
            denied = True
        else:
            denied = False
        checks.append({"id": "sdk_unknown_binding_denied", "passed": denied})
        engine.close()
        snapshot = root / "snapshot"
        shutil.copytree(store, snapshot)
        engine = Mem0Engine(python, store, namespace_key=key)
        result = engine.call("get", own, ref=engine.ref(own, "record-a"))
        checks.append({"id": "sdk_persistent_restart", "passed": result["text_sha256"] == hashlib.sha256(b"synthetic preferred format concise").hexdigest()})
        engine.upsert(own, "record-a", "synthetic corrected format detailed")
        result = engine.call("get", own, ref=engine.ref(own, "record-a"))
        checks.append({"id": "sdk_update_readback", "passed": result["text_sha256"] == hashlib.sha256(b"synthetic corrected format detailed").hexdigest()})
        result = engine.call("delete", own, ref=engine.ref(own, "record-a"))
        retained = result["history_rows_remaining"]
        checks.append({"id": "sdk_vector_delete_readback", "passed": engine.search(own, "synthetic corrected format") == []})
        engine.close()
        restored = root / "restored"
        shutil.copytree(snapshot, restored)
        engine = Mem0Engine(python, restored, namespace_key=key)
        result = engine.call("get", own, ref=engine.ref(own, "record-a"))
        checks.append({"id": "sdk_local_snapshot_restore", "passed": result["text_sha256"] == hashlib.sha256(b"synthetic preferred format concise").hexdigest()})
        checks.append({"id": "sdk_restored_scope_filters", "passed": engine.search(own, "synthetic preferred format") == ["record-a"]})
    finally:
        engine.close()
    return {"cases": checks, "history_rows_after_vector_delete": retained,
            "complete_erasure_gate": "FAIL" if retained else "UNPROVEN",
            "snapshot_scope": "authorized disposable SDK store only; not a production restore API"}


async def run(python, root):
    from tests.support.governed_memory_benchmark import execute_case
    cases = json.loads((HERE / "cases.json").read_text())
    results = []
    for case in cases:
        engine = Mem0Engine(python, root / case["id"], namespace_key=b"synthetic-kernel-namespace-key-32")
        started = time.perf_counter()
        try:
            result = await execute_case(case, candidate_backend=KernelBackend(engine))
            expected = case.get("expected_writes", 0) if case.get("operation") == "learn" else case.get("expected_searches", 1)
            # No SDK is even constructed when canonical consent denies access.
            if (expected == 0) != (engine.commands == 0):
                result["passed"] = False
            result["sdk_commands"] = engine.commands
        except Exception:
            result = {"id": case["id"], "passed": False, "reason": "engine_case_error"}
        finally:
            try:
                isolation = engine.close()
                if isolation.get("external_attempts") != 0 or isolation.get("inference_calls") != 0:
                    result["passed"] = False
            except Exception:
                result["passed"] = False
                result["reason"] = "engine_isolation_error"
        results.append({**result, "latency_ms": round((time.perf_counter() - started) * 1000, 3)})
    try:
        actual_lifecycle = await asyncio.to_thread(lifecycle, python, root)
    except Exception:
        actual_lifecycle = {"cases": [{"id": "sdk_lifecycle", "passed": False}], "complete_erasure_gate": "UNPROVEN"}
    okay = all(r["passed"] for r in results + actual_lifecycle["cases"])
    return {"schema": 1, "status": "SDK_ENGINEERING_PASS" if okay else "FAIL",
            "candidate": "mem0", "engine_status": "EXECUTED_LOCAL_SDK", "case_count": len(results),
            "passed": sum(r["passed"] for r in results), "canonical_governance": results,
            "lifecycle": actual_lifecycle,
            "upstream": json.loads((HERE / "engine_source.json").read_text()),
            "dataset_sha256": hashlib.sha256((HERE / "cases.json").read_bytes()).hexdigest(),
            "embedding": "controlled_sha256_token_hash_128d", "neural_retrieval_quality": "NOT_RUN",
            "latency_scope": "local SDK + worker startup + canonical fixture dependencies, not provider SLA",
            "inference": "disabled; add infer=False; attempted calls fail", "cost_usd": None,
            "external_memory_transfer": False, "production_certified": False,
            "adoption_decision": "retain_gravitre_native_memory",
            "adoption_reason": "upstream vector deletion does not establish complete history erasure; no semantic-quality improvement measured",
            "letta": {"disposition": "architecture_reference_only", "engine_status": "NOT_RUN",
                      "reason": "current Letta Code agent harness is not a governed retrieval adapter; autonomous/self-editing runtime excluded"}}


def engine_interpreter_path(path):
    # Resolving a venv's python symlink selects the base interpreter and loses
    # the isolated site-packages. Preserve its path when executing the worker.
    return path.expanduser().absolute()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(ROOT):
        raise SystemExit("Write reports outside source checkout")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        raise SystemExit("Clean committed source required")
    from tests import offline_network as guard
    guard.pytest_configure(None)
    try:
        with tempfile.TemporaryDirectory(prefix="gravitre-memory-sdk-") as directory:
            report = asyncio.run(run(engine_interpreter_path(args.engine_python), Path(directory)))
        if guard._attempts:
            raise RuntimeError("Parent attempted external network")
        report["external_attempts"] = 0 if report["status"] == "SDK_ENGINEERING_PASS" else None
        report["source_dirty"] = False
        report["source_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        report["source_hashes"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in (".py", ".json", ".lock")}
    finally:
        guard.pytest_unconfigure(None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "source_sha", "engine_status", "case_count", "passed", "adoption_decision")}))
    if report["status"] != "SDK_ENGINEERING_PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
