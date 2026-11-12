"""ECO-002 offline router-method harness with controlled collaborators.

Executes the actual IntelligenceRouter.route method body extracted from source,
without importing provider clients or initializing production services. It does
not represent live connector, LLM, network, or production latency.
"""
import ast
import asyncio
import importlib.util
import json
import logging
import os
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/services/intelligence_router.py"
sys.path.insert(0, str(ROOT))
from app.services.router_stage_timing import router_sample

class Awaiting:
    def __init__(self, result): self.result = result
    async def __call__(self, *args, **kwargs):
        await asyncio.sleep(0)
        return self.result

class FakeSelf:
    def __init__(self, clarify):
        self.settings = object()
        self._sentiment = SimpleNamespace(analyze=lambda *a: {"recommended_adaptation": "none", "frustration_score": 0.0})
        self._understanding = SimpleNamespace(understand=Awaiting({"entities": []}))
        self._task_classifier = SimpleNamespace(classify=Awaiting({"classification_confidence": 0.8, "requires_action": False}))
        self._clarification = SimpleNamespace(should_clarify=Awaiting({"should_clarify": clarify, "question": "Please clarify", "reason": "test"}))
        self._context_assembler = SimpleNamespace(assemble=Awaiting({}))
        self._model_selector = SimpleNamespace(select=Awaiting({"provider": "fixture"}))
        self._risk_evaluator = SimpleNamespace(evaluate=Awaiting({}))
        self._run_enrichments = Awaiting({})
        self._route_to_knowledge_response = Awaiting({"answer": "", "confidence": 0.8})
        self._guidance = SimpleNamespace(get_suggestions=Awaiting([]))
        self._consensus = SimpleNamespace(refine_if_warranted=Awaiting({}))

class Trust:
    def wrap_response(self, **kwargs): return {"answer": kwargs["answer"]}

def route_function():
    tree = ast.parse(SOURCE.read_text())
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "IntelligenceRouter")
    method = next(x for x in cls.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "route")
    # Preserve the actual method body and awaits. Remove annotation evaluation.
    method.returns = None
    for arg in method.args.args: arg.annotation = None
    code = compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(SOURCE), "exec")
    from app.services.router_stage_timing import timed_router_stage
    namespace = {"timed_router_stage": timed_router_stage, "Any": object}
    exec(code, namespace)
    return namespace["route"]

async def run_samples(count=100):
    route = route_function()
    # Imports inside route are replaced with fixture-only modules, never network clients.
    import types
    modules = {
        "app.services.intelligence_overview_policy": {
            "load_overview_policy": lambda *a: {"adaptive": "conservative"},
            "apply_response_sensitivity": lambda result, policy: result,
        },
        "app.core.io_pool": {"run_io": lambda fn: Awaiting(fn())()},
        "app.services.knowledge_intelligence_service": {"enrich_classification_with_query_cluster": Awaiting({"classification_confidence": 0.8, "requires_action": False})},
        "app.services.domain_routing_policy": {"build_routing_metadata": lambda x: {}},
        "app.services.intelligence_visibility_service": {"get_intelligence_visibility_service": lambda *a: SimpleNamespace(is_enabled=lambda: False)},
    }
    from contextlib import ExitStack
    with ExitStack() as stack:
        for name, attrs in modules.items():
            stack.enter_context(patch.dict(sys.modules, {name: types.SimpleNamespace(**attrs)}))
        globals_ = route.__globals__
        globals_.update({
            "load_chat_dialogue_settings": Awaiting({"sentiment_detection_enabled": True}),
            "get_ai_trust_layer": lambda: Trust(),
            "build_route_strategy_key": lambda *a: "fixture",
            "parse_segment_key": lambda *a: "fixture",
            "get_dialogue_policy_engine": lambda **kw: SimpleNamespace(select_mode=lambda *a: {"mode": "answer", "reason": "fixture", "next_move": ""}),
        })
        for scenario, clarify in (("clarification", True), ("knowledge", False)):
            for i in range(count):
                with router_sample(f"{scenario}-{i:04d}"):
                    result = await route(FakeSelf(clarify), "fixture-org", "fixture-user", "synthetic routing request", surface="chat")
                    assert result["answer"] == ("Please clarify" if clarify else "")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000: parser.error("samples must be 1..1000")
    os.environ["GRAVITRE_ROUTER_STAGE_TIMING_ENABLED"] = "1"
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(run_samples(args.samples))
