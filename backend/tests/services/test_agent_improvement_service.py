"""Model Studio "Improve agent": improvements land in the stores runtime reads."""
from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.operators.agent_intelligence import resolve_agent_record
from app.services.agent_finetune_service import (
    assign_trained_model_to_agent,
    resolve_agent_inference_model,
)
from app.services.agent_improvement_service import (
    ImprovementRequest,
    apply_agent_improvements,
    read_agent_improvement_state,
)
from app.services.training_service import load_active_instruction_texts

ORG = "org-1"
OTHER_ORG = "org-2"
ACTOR = "11111111-1111-1111-1111-111111111111"


class _Query:
    def __init__(self, db: FakeDb, table: str) -> None:
        self.db = db
        self.table = table
        self.filters: list[tuple[str, str, Any]] = []
        self.op = "select"
        self.payload: Any = None
        self._limit: int | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> _Query:
        return self

    def insert(self, payload: Any) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def eq(self, key: str, value: Any) -> _Query:
        self.filters.append(("eq", key, value))
        return self

    def is_(self, key: str, value: Any) -> _Query:
        self.filters.append(("is", key, value))
        return self

    def in_(self, key: str, values: list[Any]) -> _Query:
        self.filters.append(("in", key, values))
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> _Query:
        return self

    def limit(self, n: int) -> _Query:
        self._limit = n
        return self

    def _match(self, row: dict[str, Any]) -> bool:
        for kind, key, value in self.filters:
            if kind == "eq" and row.get(key) != value:
                return False
            if kind == "is" and value == "null" and row.get(key) is not None:
                return False
            if kind == "in" and row.get(key) not in value:
                return False
        return True

    def execute(self) -> SimpleNamespace:
        rows = self.db.tables.setdefault(self.table, [])
        if self.table in self.db.fail_tables:
            raise RuntimeError(f"{self.table} unavailable")
        if self.op == "insert":
            items = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for item in items:
                row = {"id": str(uuid.uuid4()), **copy.deepcopy(item)}
                rows.append(row)
                out.append(copy.deepcopy(row))
            return SimpleNamespace(data=out, error=None)
        matched = [row for row in rows if self._match(row)]
        if self.op == "update":
            for row in matched:
                row.update(copy.deepcopy(self.payload))
            return SimpleNamespace(data=[copy.deepcopy(r) for r in matched], error=None)
        if self._limit is not None:
            matched = matched[: self._limit]
        return SimpleNamespace(data=[copy.deepcopy(r) for r in matched], error=None)


class FakeDb:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = tables
        self.fail_tables: set[str] = set()

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _db(**extra: list[dict[str, Any]]) -> FakeDb:
    tables: dict[str, list[dict[str, Any]]] = {
        "agents": [
            {"id": "agent-1", "org_id": ORG, "name": "Sales", "model": "gpt-5.4-mini", "trained_model_id": None, "config": {}},
        ],
        "operators": [
            {"id": "op-1", "org_id": ORG, "name": "Legacy", "role": "Support", "status": "active", "config": {"model": "gpt-5.4-mini"}},
        ],
        "trained_models": [
            {"id": "ft-1", "org_id": ORG, "model_type": "fine_tuned_llm", "status": "deployed", "name": "Tone", "base_model": "gpt-4.1", "deployed_version": 1, "current_version": 1},
            {"id": "ft-draft", "org_id": ORG, "model_type": "fine_tuned_llm", "status": "draft", "name": "Draft"},
        ],
        "model_versions": [
            {"model_id": "ft-1", "version": 1, "metrics": {"custom_metrics": {"fine_tuned_model": "ft:gpt-4.1:org:tone"}}},
        ],
        "custom_instructions": [],
        "agent_knowledge_assignments": [],
        "rag_sources": [
            {"id": "src-1", "org_id": ORG, "name": "Pricing docs", "deleted_at": None},
            {"id": "src-other", "org_id": OTHER_ORG, "name": "Not ours", "deleted_at": None},
        ],
    }
    tables.update(extra)
    return FakeDb(tables)


@pytest.fixture(autouse=True)
def _no_audit():
    with patch("app.services.agent_improvement_service.write_audit_event") as audit, patch(
        "app.services.agent_finetune_service.write_audit_event"
    ):
        yield audit


def _steps(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f"{s['kind']}:{s['target']}": s for s in result["steps"]}


def test_applies_all_improvements_to_agents_row_and_verifies(_no_audit):
    db = _db()
    result = apply_agent_improvements(
        db,
        org_id=ORG,
        agent_id="agent-1",
        actor_id=ACTOR,
        request=ImprovementRequest(
            instruction_content="Always quote list price in USD.",
            model="claude-sonnet-4-6",
            trained_model_id="ft-1",
            knowledge_source_ids=["src-1"],
        ),
    )
    assert result["failedCount"] == 0
    assert result["appliedCount"] == 4
    assert all(step["verified"] for step in result["steps"])

    agent = db.tables["agents"][0]
    assert agent["model"] == "claude-sonnet-4-6"
    assert agent["trained_model_id"] == "ft-1"
    # Runtime reads: instruction text injection and fine-tune resolution.
    texts = load_active_instruction_texts(db, ORG, agent_id="agent-1")
    assert any("Always quote list price in USD." in t for t in texts)
    assert load_active_instruction_texts(db, ORG, agent_id="someone-else") == []
    record = resolve_agent_record(db, ORG, "agent-1")
    assert resolve_agent_inference_model(db, ORG, record).fine_tuned_openai_id == "ft:gpt-4.1:org:tone"
    assignment = db.tables["agent_knowledge_assignments"][0]
    assert (assignment["agent_id"], assignment["source_type"], assignment["source_id"]) == ("agent-1", "rag_source", "src-1")

    _no_audit.assert_called_once()
    assert _no_audit.call_args.kwargs["action"] == "agent.improvements.applied"


def test_reapplying_same_improvements_is_unchanged_not_duplicated():
    db = _db()
    req = ImprovementRequest(instruction_content="Be brief.", model="gpt-5.5", knowledge_source_ids=["src-1"])
    apply_agent_improvements(db, org_id=ORG, agent_id="agent-1", actor_id=ACTOR, request=req)
    again = apply_agent_improvements(db, org_id=ORG, agent_id="agent-1", actor_id=ACTOR, request=req)
    assert {s["status"] for s in again["steps"]} == {"unchanged"}
    assert all(s["verified"] for s in again["steps"])
    assert len(db.tables["custom_instructions"]) == 1
    assert len(db.tables["agent_knowledge_assignments"]) == 1


def test_one_failed_step_does_not_block_others():
    db = _db()
    result = apply_agent_improvements(
        db,
        org_id=ORG,
        agent_id="agent-1",
        actor_id=ACTOR,
        request=ImprovementRequest(model="gpt-5.5", trained_model_id="ft-draft", knowledge_source_ids=["src-other"]),
    )
    steps = _steps(result)
    assert steps["model:gpt-5.5"]["status"] == "applied" and steps["model:gpt-5.5"]["verified"]
    assert steps["fine_tune:ft-draft"]["status"] == "failed"
    assert "ready or deployed" in steps["fine_tune:ft-draft"]["message"]
    # Another org's knowledge source is not attachable.
    assert steps["knowledge:src-other"]["status"] == "failed"
    assert db.tables["agents"][0]["trained_model_id"] is None
    assert db.tables["agent_knowledge_assignments"] == []


def test_auto_model_is_rejected():
    db = _db()
    result = apply_agent_improvements(
        db, org_id=ORG, agent_id="agent-1", actor_id=ACTOR, request=ImprovementRequest(model="auto")
    )
    assert result["steps"][0]["status"] == "failed"
    assert db.tables["agents"][0]["model"] == "gpt-5.4-mini"


def test_operator_only_agent_gets_model_instruction_and_fine_tune_in_config():
    db = _db()
    result = apply_agent_improvements(
        db,
        org_id=ORG,
        agent_id="op-1",
        actor_id=ACTOR,
        request=ImprovementRequest(
            instruction_content="Escalate refunds over $500.",
            model="gpt-5.5",
            trained_model_id="ft-1",
            knowledge_source_ids=["src-1"],
        ),
    )
    steps = _steps(result)
    assert steps["model:gpt-5.5"]["verified"]
    assert steps["fine_tune:ft-1"]["verified"]
    assert steps["instruction:Model Studio note"]["verified"]
    assert steps["knowledge:src-1"]["status"] == "failed"
    assert result["state"]["supportsKnowledge"] is False

    record = resolve_agent_record(db, ORG, "op-1")
    assert record is not None
    assert record["model"] == "gpt-5.5"
    assert "Escalate refunds over $500." in record["config"]["system_prompt"]
    inference = resolve_agent_inference_model(db, ORG, record)
    assert inference.fine_tuned_openai_id == "ft:gpt-4.1:org:tone"


def test_unknown_or_cross_org_agent_is_404():
    db = _db()
    with pytest.raises(HTTPException) as exc:
        apply_agent_improvements(
            db, org_id=OTHER_ORG, agent_id="agent-1", actor_id=ACTOR, request=ImprovementRequest(model="gpt-5.5")
        )
    assert exc.value.status_code == 404
    assert db.tables["agents"][0]["model"] == "gpt-5.4-mini"


def test_empty_request_is_rejected():
    with pytest.raises(HTTPException) as exc:
        apply_agent_improvements(
            _db(), org_id=ORG, agent_id="agent-1", actor_id=ACTOR, request=ImprovementRequest()
        )
    assert exc.value.status_code == 400


def test_state_reports_runtime_values():
    db = _db()
    db.tables["custom_instructions"].append(
        {"id": "i1", "org_id": ORG, "agent_id": "agent-1", "name": "N", "content": "C", "is_active": True}
    )
    state = read_agent_improvement_state(db, ORG, "agent-1")
    assert state["storage"] == "agent"
    assert state["model"] == "gpt-5.4-mini"
    assert [i["content"] for i in state["instructions"]] == ["C"]


# --- Bug 1: fine-tunes on operator-backed agents ---------------------------


def test_resolve_agent_record_carries_operator_trained_model_id():
    db = _db()
    db.tables["operators"][0]["config"] = {"trained_model_id": "ft-1"}
    record = resolve_agent_record(db, ORG, "op-1")
    assert record is not None and record["trained_model_id"] == "ft-1"
    assert resolve_agent_inference_model(db, ORG, record).fine_tuned_openai_id == "ft:gpt-4.1:org:tone"


def test_assign_trained_model_falls_back_to_operator_config():
    db = _db()
    result = assign_trained_model_to_agent(
        db, org_id=ORG, agent_id="op-1", trained_model_id="ft-1", actor_id=ACTOR
    )
    assert result["trained_model_id"] == "ft-1"
    assert db.tables["operators"][0]["config"] == {"model": "gpt-5.4-mini", "trained_model_id": "ft-1"}

    cleared = assign_trained_model_to_agent(db, org_id=ORG, agent_id="op-1", trained_model_id=None, actor_id=ACTOR)
    assert cleared["trained_model_id"] is None
    assert "trained_model_id" not in db.tables["operators"][0]["config"]


def test_assign_trained_model_unknown_agent_still_404():
    with pytest.raises(HTTPException) as exc:
        assign_trained_model_to_agent(
            _db(), org_id=ORG, agent_id="missing", trained_model_id="ft-1", actor_id=ACTOR
        )
    assert exc.value.status_code == 404
