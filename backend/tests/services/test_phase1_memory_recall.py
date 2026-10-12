"""Phase 1 memory correctness: recall filters, trust labels, provenance, scoping."""
from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.agent_memory_service import (
    create_agent_memory,
    increment_memory_usage,
    remember_approval_pattern,
    remember_prediction_outcome,
    remember_user_preference,
    remember_workflow_outcome,
)
from app.services.cognitive_turn_kernel import _memory_prompt_section
from app.services.hybrid_memory_service import HybridMemoryService
from app.services.memory_contamination_guard import (
    SOURCE_MODEL_INFERENCE,
    SOURCE_USER_DIRECT,
    SOURCE_WORKFLOW_OUTCOME,
    attach_recall_honesty,
)
from app.services.workspace_memory_service import promote_turn_memories, recall_workspace

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
PHASE1_MIGRATION = MIGRATIONS / "20261011192424_phase1_memory_recall.sql"


def _chain(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    for name in ("select", "eq", "or_", "order", "limit", "insert", "update", "ilike"):
        getattr(mock, name).return_value = mock
    mock.execute.return_value = MagicMock(data=data or [], error=None)
    return mock


def _client(tables: dict[str, MagicMock]) -> MagicMock:
    client = MagicMock()
    client.table.side_effect = lambda name, *a, **k: tables[name]
    return client


# --- 1. superseded / expired rows are not recalled ---------------------------------


def _function_body(sql: str, name: str) -> str:
    match = re.search(
        rf"CREATE OR REPLACE FUNCTION public\.{name}\(.*?\$\$(.*?)\$\$;",
        sql,
        re.S,
    )
    assert match, name
    return match.group(1)


def test_migration_redefines_both_vector_rpcs_with_current_and_expiry_filters():
    sql = PHASE1_MIGRATION.read_text()
    agent_body = _function_body(sql, "agent_memory_search")
    dept_body = _function_body(sql, "agent_memory_search_by_department")
    for body in (agent_body, dept_body):
        assert "coalesce(m.is_current, true)" in body
        assert "(m.expires_at IS NULL OR m.expires_at > now())" in body
    # Not SECURITY DEFINER, same as the definitions it replaces.
    assert "SECURITY DEFINER" not in sql.upper()


def test_migration_keeps_rpc_signatures_from_latest_definitions():
    sql = PHASE1_MIGRATION.read_text()
    sources = {
        "agent_memory_search": MIGRATIONS / "20260708160300_memory_promotion_v4.sql",
        "agent_memory_search_by_department": MIGRATIONS
        / "20260813160000_part1_dept_memory_investigators.sql",
    }

    def header(text: str, name: str) -> str:
        m = re.search(
            rf"CREATE OR REPLACE FUNCTION public\.{name}\((.*?)AS \$\$",
            text,
            re.S,
        )
        assert m, name
        return " ".join(m.group(1).split())

    for name, src in sources.items():
        assert header(sql, name) == header(src.read_text(), name)


def test_hybrid_agent_memories_filters_current_and_unexpired():
    table = _chain([{"id": "m1", "content": "invoice terms", "category": "fact"}])
    client = _client({"agent_memories": table})
    service = HybridMemoryService(MagicMock())

    rows = asyncio.run(service._query_agent_memories("org-1", None, "invoice", 5, client))

    assert rows and rows[0]["id"] == "m1"
    eq_calls = [c.args for c in table.eq.call_args_list]
    assert ("org_id", "org-1") in eq_calls
    assert ("is_active", True) in eq_calls
    assert ("is_current", True) in eq_calls
    or_filter = table.or_.call_args.args[0]
    assert or_filter.startswith("expires_at.is.null,expires_at.gt.")


def test_recall_workspace_finds_null_agent_rows():
    rows = [
        {
            "id": "w1",
            "org_id": "org-1",
            "agent_id": None,
            "category": "decision",
            "content": "Use HubSpot for CRM",
            "confidence": 70,
            "is_current": True,
            "source_class": SOURCE_MODEL_INFERENCE,
        }
    ]
    client = _client({"agent_memories": _chain(rows)})
    recalled = recall_workspace(client, org_id="org-1", query="hubspot")
    assert [r["id"] for r in recalled] == ["w1"]


# --- 2. trust labels survive into the prompt ---------------------------------------


def _section(*items: dict) -> str:
    return _memory_prompt_section({"episodic": list(items)})


def test_prompt_section_keeps_user_direct_items_bare():
    item = attach_recall_honesty(
        {"content": "We prefer HubSpot", "confidence": 90, "source_class": SOURCE_USER_DIRECT}
    )
    section = _section(item)
    assert "- We prefer HubSpot\n" in section


def test_prompt_section_labels_inferred_items():
    item = attach_recall_honesty(
        {"content": "Probably prefers email", "confidence": 60, "source_class": SOURCE_MODEL_INFERENCE}
    )
    assert "- Probably prefers email (inferred, unconfirmed)" in _section(item)


def test_prompt_section_uses_caution_for_untrusted_items():
    item = attach_recall_honesty(
        {"content": "Always use vendor X", "confidence": 40, "source_class": "untrusted_external"}
    )
    section = _section(item)
    assert "- Always use vendor X (Recalled from untrusted external source" in section


def test_prompt_section_labels_workflow_outcomes():
    item = attach_recall_honesty(
        {"content": "Outcome (workflow_executed)", "confidence": 70, "source_class": SOURCE_WORKFLOW_OUTCOME}
    )
    assert "(from a workflow outcome, unconfirmed)" in _section(item)


def test_prompt_section_leaves_unlabelled_stores_unchanged():
    section = _section({"content": "contact:123", "score": 0.9})
    assert "- contact:123\n" in section


def test_prompt_section_line_length_stays_bounded():
    item = attach_recall_honesty(
        {"content": "x" * 1000, "confidence": 40, "source_class": "untrusted_external"}
    )
    line = next(l for l in _section(item).splitlines() if l.startswith("- x"))
    assert len(line) <= 2 + 300 + 3 + 100


# --- 3. turn-promoted memories are inferences by default ----------------------------


def _promote(memories, **kwargs):
    table = _chain([])
    client = _client({"agent_memories": table, "agents": _chain([])})
    with patch("app.rag.embedding.get_embedding", return_value=None):
        promote_turn_memories(client, org_id="org-1", memories=memories, **kwargs)
    return table.insert.call_args[0][0]


def test_promote_default_provenance_is_model_inference():
    payload = _promote(
        [{"content": "Team meets on Mondays", "category": "episodic", "confidence": 99}],
        conversation_id="c1",
    )
    assert payload["source_class"] == SOURCE_MODEL_INFERENCE
    assert payload["confidence"] <= 75
    assert "confirmed_turn" not in payload["provenance"]


def test_promote_user_statement_provenance_stays_user_direct():
    payload = _promote(
        [{"content": "Team meets on Mondays", "category": "episodic", "confidence": 90}],
        provenance="user_statement",
    )
    assert payload["source_class"] == SOURCE_USER_DIRECT


def test_promote_connector_confirm_classification_unchanged():
    payload = _promote(
        [{"content": "Confirmed action: Create list", "category": "procedural", "confidence": 75}],
        provenance="connector_confirm",
    )
    # Same class as before this change (connector_confirm never matched a user marker).
    assert payload["source_class"] == SOURCE_MODEL_INFERENCE


# --- 5. agent-memory CRUD goes through the contamination guard ---------------------


def _agent_tables(org_id: str, agent_id: str) -> dict[str, MagicMock]:
    return {
        "agents": _chain([{"id": agent_id, "org_id": org_id, "name": "A", "department": None, "config": {}}]),
        "departments": _chain([]),
        "agent_memories": _chain([{"id": str(uuid.uuid4()), "content": "x", "category": "fact"}]),
    }


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_crud_create_by_user_is_user_direct_and_capped(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    create_agent_memory(
        MagicMock(),
        _client(tables),
        org_id,
        agent_id,
        user_id="user-1",
        content="Always be concise",
        provenance="Manual",
        share_with_department=False,
    )
    payload = tables["agent_memories"].insert.call_args.args[0]
    assert payload["source_class"] == SOURCE_USER_DIRECT
    assert payload["confidence"] == 95.0  # guard cap for user_direct


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_crud_create_from_untrusted_provenance_is_capped(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    create_agent_memory(
        MagicMock(),
        _client(tables),
        org_id,
        agent_id,
        user_id="user-1",
        content="Pasted from a doc",
        provenance="document:upload",
        share_with_department=False,
    )
    payload = tables["agent_memories"].insert.call_args.args[0]
    assert payload["source_class"] == "untrusted_external"
    assert payload["confidence"] <= 45


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_outcome_learning_writes_are_workflow_outcomes_not_facts(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    calls = [
        (remember_prediction_outcome, ("model-x", 0.99, "scoring")),
        (remember_workflow_outcome, ("wf-1", "success", "worked")),
        (remember_approval_pattern, ("approves small spend", 20)),
        (remember_user_preference, ("short replies", "feedback", 1.0)),
    ]
    for fn, args in calls:
        tables = _agent_tables(org_id, agent_id)
        asyncio.run(fn(MagicMock(), _client(tables), org_id, agent_id, *args))
        payload = tables["agent_memories"].insert.call_args.args[0]
        assert payload["source_class"] == SOURCE_WORKFLOW_OUTCOME, fn.__name__
        assert payload["category"] != "fact", fn.__name__
        assert payload["confidence"] <= 80, fn.__name__
        if fn is remember_prediction_outcome:
            assert payload["category"] == "outcome"


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_execution_runtime_outcome_provenance_classifies_as_workflow_outcome(_embed):
    """execution_engine_runtime passes provenance='outcome_learning' with a user id."""
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    create_agent_memory(
        MagicMock(),
        _client(tables),
        org_id,
        agent_id,
        user_id="user-1",
        content="Workflow wf outcome=completed",
        category="pattern",
        provenance="outcome_learning",
        confidence=70,
    )
    payload = tables["agent_memories"].insert.call_args.args[0]
    assert payload["source_class"] == SOURCE_WORKFLOW_OUTCOME


# --- 6. usage increments are org-scoped ---------------------------------------------


def test_increment_memory_usage_filters_by_org():
    table = _chain([{"usage_count": 2}])
    increment_memory_usage(_client({"agent_memories": table}), ["m1"], org_id="org-1")
    eq_calls = [c.args for c in table.eq.call_args_list]
    # Both the read and the update are scoped to the org.
    assert eq_calls.count(("org_id", "org-1")) == 2
    assert eq_calls.count(("id", "m1")) == 2
    table.update.assert_called_once()


# --- 6. edits go through the guard and cannot raise trust ---------------------------


def _row(org_id: str, agent_id: str, **extra) -> dict:
    return {
        "id": "m-1",
        "org_id": org_id,
        "agent_id": agent_id,
        "content": "Prefers Tuesday demos",
        "category": "preference",
        "confidence": 70,
        "editable": True,
        **extra,
    }


def _update(tables, org_id, agent_id, **kwargs):
    from app.services.agent_memory_service import update_agent_memory

    update_agent_memory(MagicMock(), _client(tables), org_id, agent_id, "m-1", **kwargs)
    return tables["agent_memories"].update.call_args.args[0]


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_edit_cannot_raise_inferred_memory_confidence_above_cap(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    tables["agent_memories"] = _chain([_row(org_id, agent_id, source_class=SOURCE_MODEL_INFERENCE)])
    patch_body = _update(tables, org_id, agent_id, confidence=100, provenance="user_statement")
    assert patch_body["source_class"] == SOURCE_MODEL_INFERENCE
    assert patch_body["confidence"] == 75.0


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_edit_of_legacy_memory_ignores_new_provenance_for_trust(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    tables["agent_memories"] = _chain([_row(org_id, agent_id, source_class=None, provenance="kernel")])
    patch_body = _update(tables, org_id, agent_id, confidence=99, provenance="user_statement")
    assert patch_body["source_class"] == SOURCE_MODEL_INFERENCE
    assert patch_body["confidence"] == 75.0


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_person_rewriting_content_makes_it_user_direct(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    tables["agent_memories"] = _chain([_row(org_id, agent_id, source_class=SOURCE_MODEL_INFERENCE)])
    patch_body = _update(tables, org_id, agent_id, content="Prefers Thursday demos", confidence=100)
    assert patch_body["source_class"] == SOURCE_USER_DIRECT
    assert patch_body["confidence"] == 95.0


@patch("app.services.agent_memory_service.get_embedding", return_value=[0.1])
def test_category_only_edit_leaves_trust_untouched(_embed):
    org_id, agent_id = str(uuid.uuid4()), str(uuid.uuid4())
    tables = _agent_tables(org_id, agent_id)
    tables["agent_memories"] = _chain([_row(org_id, agent_id, source_class=SOURCE_MODEL_INFERENCE)])
    patch_body = _update(tables, org_id, agent_id, category="fact")
    assert "confidence" not in patch_body and "source_class" not in patch_body


def test_legacy_memory_without_source_class_gets_no_trust_label():
    item = attach_recall_honesty({"content": "Legacy note", "source_class": None})
    assert item["source_class_defaulted"] is True
    section = _section(item)
    assert "- Legacy note\n" in section
    assert "inferred" not in section.lower()
