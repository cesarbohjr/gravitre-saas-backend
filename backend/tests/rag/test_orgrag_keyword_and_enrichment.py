"""Phase 3: the org RAG keyword arm's real reach, and contextual enrichment.

Phase 3 was scoped on the premise that org RAG "has no persisted keyword index
... unlike the Knowledge Fabric which already has one" and needs bringing "up to
the same real, hybrid standard". Half of that was true and half was not, and the
difference is the whole point of these tests.

Org RAG was ALREADY hybrid: vector RPC, BM25 keyword arm, RRF merge,
cross-encoder rerank. In one respect it was better than the Fabric, whose FTS
arm cannot order by ts_rank at all -- BM25 produces a real relevance order.

The actual defect was in what BM25 got to rank. `fetch_bm25_corpus` fetched 500
rows with no query terms and no ORDER BY, so it ranked an arbitrary slice of the
corpus. Under 500 chunks that is exact and looks perfect; over 500 it silently
becomes a sample, and nothing reported which regime an org was in. Measured
before fixing: docs/delivery/orgrag-keyword-reach.json, one chunk platform-wide,
so this was a latent trap rather than a live defect.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.rag import retrieval as rag_retrieval
from app.rag.contextual_enrichment import (
    ENRICH_DISABLED,
    ENRICH_FAILED,
    ENRICH_NO_SYNOPSIS,
    ENRICH_OK,
    build_chunk_context,
    build_document_synopsis,
    enrichment_enabled,
    summarize_enrichment,
    text_for_embedding,
)
from app.rag.retrieval import (
    REACH_EMPTY,
    REACH_EXACT,
    REACH_FTS,
    REACH_NO_TERMS,
    REACH_TRUNCATED,
    fetch_bm25_corpus,
)

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase"
    / "migrations"
    / "20260903100000_rag_chunks_fts.sql"
)


# --------------------------------------------------------------------------
# The keyword arm's reach
# --------------------------------------------------------------------------


class _FakeBuilder:
    """Records the postgrest call chain so the ORDER of calls can be asserted.

    Ordering is not a detail here: `text_search` returns a QueryRequestBuilder
    with no `.limit()`, so calling them the wrong way round raises
    AttributeError inside a try/except and silently kills the keyword arm. That
    is precisely how the Fabric's arm stayed dead for months.
    """

    def __init__(self, log: list[str], rows: list[dict], fail_text_search: bool = False):
        self._log = log
        self._rows = rows
        self._fail = fail_text_search
        self.text_search_args: tuple[Any, ...] | None = None
        self.text_search_kwargs: dict[str, Any] | None = None

    def select(self, *a, **k):
        self._log.append("select")
        return self

    def eq(self, *a, **k):
        self._log.append("eq")
        return self

    def in_(self, *a, **k):
        self._log.append("in_")
        return self

    def limit(self, *a, **k):
        self._log.append("limit")
        return self

    def range(self, *a, **k):
        return self

    def text_search(self, *a, **k):
        self._log.append("text_search")
        self.text_search_args = a
        self.text_search_kwargs = k
        if self._fail:
            raise TypeError("text_search() got an unexpected keyword argument 'config'")
        return self

    def execute(self):
        self._log.append("execute")
        return SimpleNamespace(data=list(self._rows))


class _FakeClient:
    def __init__(self, chunk_rows: list[dict], fail_text_search: bool = False):
        self.log: list[str] = []
        self._chunk_rows = chunk_rows
        self._fail = fail_text_search
        self.builders: list[_FakeBuilder] = []

    def table(self, name: str):
        if name == "rag_documents":
            return _FakeBuilder(self.log, [{"id": "doc-1", "title": "Handbook"}])
        b = _FakeBuilder(self.log, self._chunk_rows, fail_text_search=self._fail)
        self.builders.append(b)
        return b


def _settings() -> Any:
    return SimpleNamespace(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-key",
    )


def _install(monkeypatch, client) -> None:
    monkeypatch.setattr(rag_retrieval, "create_client", lambda *a, **k: client)
    monkeypatch.setattr(
        rag_retrieval, "_resolve_source_ids_for_scope", lambda *a, **k: None
    )


def _rows(n: int) -> list[dict]:
    return [
        {"id": f"c{i}", "content": f"chunk {i} text", "document_id": "doc-1", "source_id": "s1"}
        for i in range(n)
    ]


def test_the_query_reaches_postgres_instead_of_being_dropped(monkeypatch):
    """The defect in one assertion: the corpus fetch used to be query-blind."""
    client = _FakeClient(_rows(3))
    _install(monkeypatch, client)

    rows, reach = fetch_bm25_corpus(
        _settings(), "org-1", query_text="breach notification deadline Ontario"
    )
    assert reach == REACH_FTS
    assert len(rows) == 3

    builder = client.builders[0]
    assert builder.text_search_args is not None, "keyword filter never applied"
    column, query, options = builder.text_search_args
    assert column == "content_tsv"
    assert "breach" in query
    assert options == rag_retrieval.FTS_OPTIONS


def test_limit_is_applied_before_text_search(monkeypatch):
    """Reversed, this raises AttributeError inside an except and dies silently."""
    client = _FakeClient(_rows(2))
    _install(monkeypatch, client)
    fetch_bm25_corpus(_settings(), "org-1", query_text="payroll policy")

    assert "limit" in client.log and "text_search" in client.log
    assert client.log.index("limit") < client.log.index("text_search")


def test_text_search_takes_no_config_kwarg(monkeypatch):
    """postgrest's signature is (column, query, options). `config=` is a TypeError.

    Guarded at the call site as well as by behaviour, because the one defect
    that really shipped in the Fabric was the one no test looked at directly.
    """
    tree = ast.parse(inspect.getsource(rag_retrieval))
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "text_search"
    ]
    assert calls, "no text_search call — did the keyword arm get removed?"
    for node in calls:
        assert not {kw.arg for kw in node.keywords}, "text_search takes no kwargs"
        assert len(node.args) == 3, "options must be positional: (column, query, options)"


def test_truncation_is_reported_rather_than_hidden(monkeypatch):
    """The state that used to be invisible.

    A query with no usable keywords falls back to an unfiltered fetch. At the cap
    that is a SAMPLE of the corpus, and saying so is the entire fix -- BM25's
    output looks identical either way.
    """
    client = _FakeClient(_rows(500))
    _install(monkeypatch, client)
    # Stopwords only: no terms survive, so no keyword filter can be built.
    rows, reach = fetch_bm25_corpus(_settings(), "org-1", query_text="what are the")
    assert reach == REACH_TRUNCATED
    assert len(rows) == 500


def test_an_under_cap_unfiltered_fetch_is_exact_not_truncated(monkeypatch):
    client = _FakeClient(_rows(12))
    _install(monkeypatch, client)
    _, reach = fetch_bm25_corpus(_settings(), "org-1", query_text="the and of")
    assert reach in {REACH_EXACT, REACH_NO_TERMS}
    assert reach != REACH_TRUNCATED


def test_an_empty_query_is_not_applicable_rather_than_a_miss(monkeypatch):
    client = _FakeClient(_rows(4))
    _install(monkeypatch, client)
    _, reach = fetch_bm25_corpus(_settings(), "org-1", query_text="")
    assert reach == REACH_NO_TERMS


def test_no_keyword_match_is_not_reported_as_an_empty_corpus(monkeypatch):
    """A filter that ran and matched nothing is a real answer, not an absence.

    Folding it into "empty" would claim the corpus has no content when it may be
    large and simply not mention these words -- and it would make a working
    keyword arm on an unrelated query look like a broken one.
    """
    client = _FakeClient([])
    _install(monkeypatch, client)
    rows, reach = fetch_bm25_corpus(_settings(), "org-1", query_text="payroll policy")
    assert rows == []
    assert reach == rag_retrieval.REACH_FTS_NO_MATCH


def test_an_unresolvable_scope_reports_empty(monkeypatch):
    client = _FakeClient(_rows(3))
    monkeypatch.setattr(rag_retrieval, "create_client", lambda *a, **k: client)
    # Department/agent scoping resolved to zero permitted sources.
    monkeypatch.setattr(rag_retrieval, "_resolve_source_ids_for_scope", lambda *a, **k: [])
    rows, reach = fetch_bm25_corpus(_settings(), "org-1", query_text="payroll policy")
    assert rows == []
    assert reach == REACH_EMPTY


def test_fts_failure_falls_back_and_says_so(monkeypatch, caplog):
    """A broken keyword index must degrade to the old behaviour, loudly.

    Logged at WARNING with the cause interpolated into the message. The Fabric's
    identical failure was logged at INFO with the cause in `extra=`, which the
    formatter drops -- it looked instrumented and was invisible.
    """
    client = _FakeClient(_rows(3), fail_text_search=True)
    _install(monkeypatch, client)

    with caplog.at_level("WARNING"):
        rows, reach = fetch_bm25_corpus(
            _settings(), "org-1", query_text="breach notification"
        )

    assert len(rows) == 3
    assert reach != REACH_FTS
    text = caplog.text
    assert "rag_bm25_fts_unavailable" in text
    assert "config" in text, "the cause must be in the message, not in extra="


def test_reach_states_are_all_distinct():
    """Class C: two different facts must never serialise to the same value."""
    states = [
        REACH_EXACT,
        REACH_FTS,
        rag_retrieval.REACH_FTS_NO_MATCH,
        REACH_TRUNCATED,
        REACH_NO_TERMS,
        REACH_EMPTY,
    ]
    assert len(set(states)) == len(states)


def test_reach_is_returned_not_left_to_be_ignored():
    """An optional out-param would have let every caller drop the signal."""
    sig = inspect.signature(fetch_bm25_corpus)
    assert "query_text" in sig.parameters
    src = inspect.getsource(fetch_bm25_corpus)
    assert "-> tuple[list[dict[str, Any]], str]" in inspect.getsource(rag_retrieval)[
        : src.__len__() + 20000
    ] or "tuple" in str(sig.return_annotation)


def test_caller_threads_the_query_and_surfaces_the_reach():
    """The fix is only real if the one production caller actually passes it."""
    from app.services import rag_service

    src = inspect.getsource(rag_service.RAGService.retrieve_hybrid_rows)
    assert "query_text=query" in src, "corpus fetch is still query-blind at the call site"
    assert "keyword_reach" in src
    assert '"keyword_reach": keyword_reach' in inspect.getsource(rag_service)


def test_migration_mirrors_the_fabric_fts_definition():
    """Divergent stemming between the two keyword arms would be a real bug."""
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "content_tsv tsvector" in sql
    assert "to_tsvector('english'" in sql
    assert "USING gin (content_tsv)" in sql
    assert "context_prefix text" in sql


# --------------------------------------------------------------------------
# Contextual enrichment
# --------------------------------------------------------------------------


def test_enrichment_is_off_by_default():
    """Turning it on means new chunks are enriched and old ones are not.

    That mixed-corpus state should be entered deliberately, not inherited.
    """
    from app.config import Settings

    assert Settings.model_fields["rag_contextual_enrichment_enabled"].default is False
    assert enrichment_enabled(SimpleNamespace()) is False


def test_context_restores_the_referents_chunking_strips():
    """The actual failure mode, in one test.

    "revenue grew 3%" answers "how did ACME do in Q2" and will never be
    retrieved for it, because the embedding contains neither "ACME" nor "Q2".
    Those words were in the title and the opening paragraph.
    """
    chunks = [
        "ACME Corp filed its quarterly report for Q2 2026.",
        "Revenue grew 3% over the prior quarter.",
        "Headcount was unchanged.",
    ]
    context = build_chunk_context(
        chunk_index=1,
        chunks=chunks,
        title="ACME Q2 2026 Report",
        synopsis="ACME Corp's Q2 2026 quarterly financial report.",
    )
    assert "ACME" in context
    assert "Q2 2026" in context
    assert "passage 2 of 3" in context
    # Neighbours on both sides, since a middle chunk has both.
    assert "Preceded by" in context
    assert "Followed by" in context


def test_context_omits_neighbours_at_the_edges():
    chunks = ["first passage", "second passage"]
    first = build_chunk_context(chunk_index=0, chunks=chunks, title="T", synopsis="")
    last = build_chunk_context(chunk_index=1, chunks=chunks, title="T", synopsis="")
    assert "Preceded by" not in first
    assert "Followed by" in first
    assert "Preceded by" in last
    assert "Followed by" not in last


def test_a_single_chunk_document_still_gets_its_title_and_synopsis():
    context = build_chunk_context(
        chunk_index=0, chunks=["only"], title="Policy", synopsis="A leave policy."
    )
    assert "Policy" in context
    assert "A leave policy." in context
    assert "passage 1 of 1" in context


def test_enrichment_prefixes_and_never_truncates_the_chunk():
    """The excerpt is what is being retrieved; context only makes it findable.

    Enrichment that displaced the content it describes would be strictly worse
    than no enrichment.
    """
    content = "x" * 4000
    out = text_for_embedding(content=content, context="Document: Handbook.")
    assert out.startswith("Document: Handbook.")
    assert content in out


def test_no_context_leaves_the_embedded_text_byte_identical():
    """Enrichment off must be exactly the old behaviour, not nearly."""
    assert text_for_embedding(content="abc", context="") == "abc"


@pytest.mark.asyncio
async def test_synopsis_reports_disabled_distinctly_from_failed():
    """Class C again: three outcomes, three names.

    "Enrichment is off", "the model was unavailable", and "the model returned
    nothing" all leave an empty prefix behind. Only the state field tells them
    apart, and without it a switched-off feature is indistinguishable from a
    broken one.
    """
    synopsis, state = await build_document_synopsis(
        text="body", title="t", settings=SimpleNamespace(), org_id=None
    )
    assert (synopsis, state) == ("", ENRICH_DISABLED)


@pytest.mark.asyncio
async def test_a_model_failure_degrades_to_deterministic_context_not_a_failed_ingest(
    monkeypatch, caplog
):
    import app.services.model_router as mr

    def _boom():
        raise RuntimeError("router down")

    monkeypatch.setattr(mr, "get_model_router", _boom)

    with caplog.at_level("WARNING"):
        synopsis, state = await build_document_synopsis(
            text="body text",
            title="Handbook",
            settings=SimpleNamespace(rag_contextual_enrichment_enabled=True),
            org_id=None,
        )

    assert synopsis == ""
    assert state == ENRICH_FAILED
    assert "rag_synopsis_failed" in caplog.text
    assert "router down" in caplog.text, "cause must be in the message"

    # And the deterministic half still works without it.
    context = build_chunk_context(
        chunk_index=0, chunks=["a", "b"], title="Handbook", synopsis=synopsis
    )
    assert "Handbook" in context


@pytest.mark.asyncio
async def test_empty_document_is_no_synopsis_not_a_failure():
    synopsis, state = await build_document_synopsis(
        text="   ",
        title="t",
        settings=SimpleNamespace(rag_contextual_enrichment_enabled=True),
        org_id=None,
    )
    assert (synopsis, state) == ("", ENRICH_NO_SYNOPSIS)


def test_partial_enrichment_is_not_rounded_up_to_enriched():
    assert summarize_enrichment([ENRICH_OK, ENRICH_OK])["fully_enriched"] is True
    mixed = summarize_enrichment([ENRICH_OK, ENRICH_NO_SYNOPSIS])
    assert mixed["fully_enriched"] is False
    assert mixed["enriched"] == 1
    assert summarize_enrichment([])["fully_enriched"] is False


def test_ingest_embeds_the_enriched_text_and_persists_the_prefix(monkeypatch):
    """Two separate claims, both required.

    Embedding the bare text while storing a prefix would make the column a lie.
    Storing nothing while embedding the enrichment would make it unauditable.
    """
    from app.rag import ingest as ingest_mod

    embedded: list[str] = []
    inserted: dict[str, list[dict]] = {"rag_chunks": [], "rag_embeddings": []}

    class _B:
        def __init__(self, name):
            self.name = name

        def insert(self, rows):
            self._rows = rows if isinstance(rows, list) else [rows]
            return self

        def execute(self):
            inserted[self.name].extend(self._rows)
            return SimpleNamespace(
                data=[{"id": f"chunk-{i}"} for i in range(len(self._rows))]
            )

    client = SimpleNamespace(table=lambda n: _B(n))

    monkeypatch.setattr(
        ingest_mod, "get_embedding", lambda text, s: (embedded.append(text) or [0.0])
    )
    monkeypatch.setattr(ingest_mod, "record_embedding_cost", lambda *a, **k: None)

    settings = SimpleNamespace(
        openai_api_key="sk-x",
        embedding_model="text-embedding-3-small",
        rag_contextual_enrichment_enabled=True,
    )

    ingest_mod.replace_chunks_and_embeddings(
        client,
        settings,
        "org-1",
        source_id="s1",
        document_id="d1",
        chunks=["Revenue grew 3%.", "Headcount was flat."],
        title="ACME Q2 2026",
        synopsis="ACME Corp Q2 2026 report.",
    )

    assert len(embedded) == 2
    assert all("ACME" in text for text in embedded), "embedded the bare chunk"
    assert "Revenue grew 3%." in embedded[0]

    prefixes = [row.get("context_prefix") for row in inserted["rag_chunks"]]
    assert all(p and "ACME" in p for p in prefixes), "prefix not persisted"
    # content must be untouched: it is the only thing ever shown or cited.
    contents = [row["content"] for row in inserted["rag_chunks"]]
    assert contents == ["Revenue grew 3%.", "Headcount was flat."]


def test_ingest_with_enrichment_off_is_unchanged(monkeypatch):
    from app.rag import ingest as ingest_mod

    embedded: list[str] = []
    rows_seen: list[dict] = []

    class _B:
        def __init__(self, name):
            self.name = name

        def insert(self, rows):
            self._rows = rows if isinstance(rows, list) else [rows]
            if self.name == "rag_chunks":
                rows_seen.extend(self._rows)
            return self

        def execute(self):
            return SimpleNamespace(
                data=[{"id": f"chunk-{i}"} for i in range(len(self._rows))]
            )

    client = SimpleNamespace(table=lambda n: _B(n))
    monkeypatch.setattr(
        ingest_mod, "get_embedding", lambda text, s: (embedded.append(text) or [0.0])
    )
    monkeypatch.setattr(ingest_mod, "record_embedding_cost", lambda *a, **k: None)

    ingest_mod.replace_chunks_and_embeddings(
        client,
        SimpleNamespace(
            openai_api_key="sk-x",
            embedding_model="m",
            rag_contextual_enrichment_enabled=False,
        ),
        "org-1",
        source_id="s1",
        document_id="d1",
        chunks=["bare one", "bare two"],
        title="T",
        synopsis="S",
    )
    assert embedded == ["bare one", "bare two"]
    assert all("context_prefix" not in row for row in rows_seen)


def test_embedding_cost_counts_what_was_actually_sent(monkeypatch):
    """Enrichment adds tokens. Billing the bare chunk under-reports real spend."""
    from app.rag import ingest as ingest_mod

    recorded: list[int] = []

    class _B:
        def __init__(self, name):
            self.name = name

        def insert(self, rows):
            self._rows = rows if isinstance(rows, list) else [rows]
            return self

        def execute(self):
            return SimpleNamespace(
                data=[{"id": f"chunk-{i}"} for i in range(len(self._rows))]
            )

    monkeypatch.setattr(ingest_mod, "get_embedding", lambda text, s: [0.0])
    monkeypatch.setattr(
        ingest_mod,
        "record_embedding_cost",
        lambda s, o, p, m, tokens: recorded.append(tokens),
    )

    long_synopsis = "ACME Corp quarterly financial report for the period. " * 5
    ingest_mod.replace_chunks_and_embeddings(
        SimpleNamespace(table=lambda n: _B(n)),
        SimpleNamespace(
            openai_api_key="sk-x",
            embedding_model="m",
            rag_contextual_enrichment_enabled=True,
        ),
        "org-1",
        source_id="s1",
        document_id="d1",
        chunks=["short"],
        title="ACME Q2 2026 Report",
        synopsis=long_synopsis,
    )
    bare_tokens = ingest_mod._estimate_tokens("short")
    assert recorded and recorded[0] > bare_tokens
