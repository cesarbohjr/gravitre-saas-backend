"""Every ``getattr(settings, "name", default)`` in backend/app names a real Settings attribute.

A name Settings does not define always returns the code default, so the env var
an operator sets for it is silently ignored. Settings objects are recognised by
the first argument's source (``settings``, ``self.settings``, ``active_settings``,
``cfg``, ...). Add a name to ``ALLOWED_MISSING`` only with the reason it is not a
Settings attribute.
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.config import Settings

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# name -> reason. Keep empty unless a getattr on a settings-like object is
# deliberately reading something that is not a Settings attribute.
ALLOWED_MISSING: dict[str, str] = {}


def _is_settings_expr(src: str) -> bool:
    lowered = src.lower()
    return "settings" in lowered or lowered == "cfg"


def _settings_getattr_names() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(APP_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"getattr", "hasattr"}
                and len(node.args) >= 2
            ):
                continue
            name = node.args[1]
            if not (isinstance(name, ast.Constant) and isinstance(name.value, str)):
                continue
            if _is_settings_expr(ast.unparse(node.args[0])):
                where = f"{path.relative_to(APP_DIR.parent)}:{node.lineno}"
                found.setdefault(name.value, []).append(where)
    return found


def _defined_on_settings(name: str) -> bool:
    # Fields, plus properties such as ``embedding_model`` and ``gemini_key``.
    return name in Settings.model_fields or hasattr(Settings, name)


def test_scan_finds_settings_getattrs() -> None:
    names = _settings_getattr_names()
    # Sanity: the scan sees the call sites this test exists for.
    assert "disable_ingestion" in names
    assert "cache_warming_interval_seconds" in names


def test_every_settings_getattr_name_exists_on_settings() -> None:
    missing = {
        name: sites
        for name, sites in _settings_getattr_names().items()
        if not _defined_on_settings(name) and name not in ALLOWED_MISSING
    }
    assert not missing, (
        "getattr(settings, ...) names with no Settings field (they always fall back to the code "
        f"default): {missing}"
    )


def test_allowlist_entries_are_still_needed_and_explained() -> None:
    names = _settings_getattr_names()
    for name, reason in ALLOWED_MISSING.items():
        assert reason.strip(), name
        assert name in names and not _defined_on_settings(name), f"stale allowlist entry {name}"


def test_new_fields_keep_the_code_defaults() -> None:
    """The fields added for previously dead names default to what the code fell back to."""
    from app.services.intelligence_orchestrator import (
        DEFAULT_SPOKEN_MEDIUM_RETRIEVAL_BUDGET_MS,
        spoken_medium_retrieval_budget_s,
    )
    from app.services.pipecat_voice.utterance_gate import (
        DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE,
        min_short_transcript_confidence,
    )
    from app.services.pipecat_voice.voice_silence_guard import (
        DEFAULT_SLOW_TOOL_NOTICE_SECONDS,
        slow_tool_notice_seconds,
    )

    s = Settings()
    assert s.cache_warming_interval_seconds == 3600
    assert s.workflow_failure_prediction_interval_seconds == 3600
    assert s.context_compiler_unified_live_v1 is True
    assert s.voice_medium_retrieval_budget_ms == DEFAULT_SPOKEN_MEDIUM_RETRIEVAL_BUDGET_MS
    assert spoken_medium_retrieval_budget_s(s) == DEFAULT_SPOKEN_MEDIUM_RETRIEVAL_BUDGET_MS / 1000.0
    assert s.voice_min_short_transcript_confidence == DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE
    assert min_short_transcript_confidence(s) == DEFAULT_MIN_SHORT_TRANSCRIPT_CONFIDENCE
    assert s.voice_slow_tool_notice_seconds == DEFAULT_SLOW_TOOL_NOTICE_SECONDS
    assert slow_tool_notice_seconds(s) == DEFAULT_SLOW_TOOL_NOTICE_SECONDS


def test_confluence_credentials_still_fall_back_to_jira_and_can_be_overridden() -> None:
    from app.connectors.confluence_oauth import confluence_credentials

    s = Settings(jira_client_id="jira-id", jira_client_secret="jira-secret")
    assert s.confluence_client_id == "" and s.confluence_client_secret == ""
    assert confluence_credentials(s) == ("jira-id", "jira-secret")
    own = Settings(
        jira_client_id="jira-id",
        jira_client_secret="jira-secret",
        confluence_client_id="conf-id",
        confluence_client_secret="conf-secret",
    )
    assert confluence_credentials(own) == ("conf-id", "conf-secret")


def test_knowledge_fabric_labels_chunks_with_the_embedding_model_in_use(monkeypatch) -> None:
    from app.knowledge_fabric import ingest as kf_ingest
    from tests.services.fake_supabase_db import FakeSupabaseDB

    monkeypatch.setattr(kf_ingest, "get_embedding", lambda _text, _settings: [0.1, 0.2])
    db = FakeSupabaseDB()
    source_row = {
        "id": "src-1",
        "license_type": "A",
        "ingestion_method": "api",
        "commercial_use_allowed": True,
        "licence_verified": True,
    }

    def _model_versions(settings: Settings) -> set:
        db.writes.clear()
        # An older version exists, so the update path (which keeps its id) is taken.
        db.tables["knowledge_documents"] = [
            {"id": "doc-1", "source_id": "src-1", "external_id": "doc", "checksum": "old"}
        ]
        kf_ingest.replace_document_chunks(
            db,
            source_row=source_row,
            external_id="doc",
            title="t",
            content="Some platform knowledge text.",
            citation="c",
            jurisdiction=None,
            topics=[],
            settings=settings,
        )
        inserts = [w for w in db.writes if w[0] == "insert" and w[1] == "knowledge_chunks"]
        return {row["model_version"] for w in inserts for row in w[2]}

    assert _model_versions(Settings()) == {"text-embedding-3-small"}
    assert _model_versions(Settings(default_embedding_model="text-embedding-3-large")) == {
        "text-embedding-3-large"
    }
