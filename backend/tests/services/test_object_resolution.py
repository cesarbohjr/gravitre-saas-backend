"""Unit tests for the shared resolution contract and its resolvers.

Every connector read is faked at ``tool_service.invoke_tool``; all people,
records, lists and files are invented.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

import app.services.object_resolution as obr
from app.services.object_resolution import (
    CAPABILITIES,
    Account,
    FileRequest,
    ResolutionCandidate,
    body_with_file_link,
    cant_search_yet,
    decide,
    extract_file_request,
    file_approval_line,
    file_question,
    pick_from,
    resolve_crm_contact,
    resolve_file,
    resolve_list,
    resolve_outlook_participant,
    revalidate_bound_targets,
    select_account,
    stale_reason,
    verify_file_access_sync,
)
from app.services.tool_types import NormalizedResult
from tests.scenarios.conversation_harness import ScenarioDB

ORG = "00000000-0000-4000-8000-00000000a001"


class FakeReads:
    """Answers ``invoke_tool`` by action; records every call."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, _ctx: Any, action: str, params: dict[str, Any] | None = None) -> NormalizedResult:
        self.calls.append((action, dict(params or {})))
        answer = self.answers.get(action)
        if callable(answer):
            answer = answer(dict(params or {}))
        if isinstance(answer, str):
            return NormalizedResult(success=False, action=action, error_code=answer, error_message=answer)
        return NormalizedResult(success=True, action=action, connector_id="conn-1", data=answer or {})


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch):
    def install(answers: dict[str, Any]) -> FakeReads:
        fake = FakeReads(answers)
        monkeypatch.setattr("app.services.tool_service.invoke_tool", fake)
        return fake

    return install


def _db(*rows: dict[str, Any]) -> ScenarioDB:
    import tests.scenarios.conversation_harness as harness

    db = ScenarioDB()
    assert "connectors" in harness.STATEFUL_TABLES
    db.tables["connectors"] = [
        {
            "org_id": ORG,
            "status": "connected",
            "environment": "production",
            "config": {},
            "deleted_at": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-10-01T00:00:00+00:00",
            **row,
        }
        for row in rows
    ]
    return db


def _kw(db: Any = None, **extra: Any) -> dict[str, Any]:
    return {"org_id": ORG, "client": db or ScenarioDB(), "settings": object(), **extra}


# --- the contract --------------------------------------------------------------


def _cand(name: str, **kw: Any) -> ResolutionCandidate:
    return ResolutionCandidate(name=name, object_id=kw.pop("object_id", name.lower()), **kw)


def test_incomplete_coverage_never_resolves_a_single_match() -> None:
    res = decide("Stephanie", [_cand("Stephanie Khan")], complete=False, source="gmail", object_type="person", reason="page_cap")
    assert res.status == "incomplete" and res.chosen is None


def test_no_candidates_is_not_found_only_when_complete() -> None:
    assert decide("x", [], complete=True, source="s", object_type="file").status == "not_found"
    assert decide("x", [], complete=False, source="s", object_type="file").status == "incomplete"


def test_draft_only_single_match_needs_confirmation() -> None:
    res = decide("Park", [_cand("Stephanie Park", evidence={"draft_only": True})], complete=True, source="gmail", object_type="person")
    assert (res.status, res.reason) == ("ambiguous", "draft_only")


def test_exact_name_resolves_only_when_complete() -> None:
    cands = [_cand("MSP"), _cand("MSP Prospects")]
    exact = decide("MSP", cands, complete=True, source="apollo", object_type="list", exact=lambda c: c.name == "MSP")
    assert exact.status == "resolved" and exact.chosen.name == "MSP"
    partial = decide("MSP", cands, complete=False, source="apollo", object_type="list", exact=lambda c: c.name == "MSP")
    assert partial.status == "ambiguous"


def test_candidate_round_trips_and_reads_old_rows() -> None:
    cand = ResolutionCandidate(
        name="Budget 2026",
        source="google_drive",
        account="conn-drive",
        object_type="file",
        object_id="f1",
        access="ok",
        resolved_at=123.0,
        account_stamp="2026-10-01",
        evidence={"folder": "Finance"},
    )
    assert ResolutionCandidate.from_dict(cand.to_dict()) == cand
    old = ResolutionCandidate.from_dict({"name": "Stephanie Khan", "address": "sk@acme.example", "source": "gmail", "account": "", "evidence": {}})
    assert old.object_id == "sk@acme.example" and old.object_type == "person" and old.resolved_at == 0.0


def test_freshness_and_account_changes_make_candidates_stale() -> None:
    now = time.time()
    acct = Account(id="gmail-work", vendor="gmail", label="me@work.example", stamp="2026-10-10")
    fresh = _cand("Stephanie", account="gmail-work", account_stamp="2026-10-10", resolved_at=now)
    assert stale_reason(fresh, [acct], now=now) == ""
    assert stale_reason(fresh, [acct], now=now + obr.CANDIDATE_TTL_S + 1) == "expired"
    assert stale_reason(fresh, [Account(id="gmail-work", vendor="gmail", label="", stamp="2026-10-11")], now=now) == "account_changed"
    assert stale_reason(fresh, [], now=now) == "account_removed"
    assert stale_reason(_cand("old"), None, now=now) == "expired"  # stored before freshness stamps


def test_select_account_named_or_default() -> None:
    work = Account(id="w", vendor="gmail", label="me@work.example", emails=("me@work.example",))
    home = Account(id="h", vendor="gmail", label="me@home.example", emails=("me@home.example",))
    assert select_account([work, home], "email Stephanie") == (work, "default")
    assert select_account([work, home], "email Stephanie from me@home.example") == (home, "named")
    assert select_account([], "email Stephanie") == (None, "vendor_default")


def test_connected_accounts_orders_like_the_send_default() -> None:
    db = _db(
        {"id": "old", "type": "gmail", "updated_at": "2026-01-01", "config": {"email": "a@x.example"}},
        {"id": "new", "type": "gmail", "updated_at": "2026-10-01", "config": {"email": "b@x.example"}},
        {"id": "gone", "type": "gmail", "status": "disconnected"},
        {"id": "other", "type": "hubspot"},
    )
    accounts = obr.connected_accounts(db, ORG, "gmail")
    assert [a.id for a in accounts] == ["new", "old"]
    assert accounts[0].label == "b@x.example" and accounts[0].stamp == "2026-10-01"


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ("The Finance one.", "f-fin"),
        ("the second one", "f-draft"),
        ("Drafts", "f-draft"),
        ("Budget 2026", None),  # fits both: picks nobody
        ("yes", None),  # two offered: "yes" is not a choice
    ],
)
def test_pick_from_files(reply: str, expected: str | None) -> None:
    files = [
        _cand("Budget 2026", object_id="f-fin", object_type="file", evidence={"folder": "Finance"}),
        _cand("Budget 2026", object_id="f-draft", object_type="file", evidence={"folder": "Drafts"}),
    ]
    picked = pick_from(reply, files)
    assert (picked.object_id if picked else None) == expected


def test_capability_table_is_honest() -> None:
    supported = {key for key, (state, _a) in CAPABILITIES.items() if state == "supported"}
    assert supported == {
        ("person", "gmail"),
        ("person", "microsoft365"),
        ("contact", "hubspot"),
        ("contact", "salesforce"),
        ("list", "apollo"),
        ("list", "constant_contact"),
        ("segment", "constant_contact"),
        ("file", "google_drive"),
        ("file", "microsoft365"),
    }
    assert cant_search_yet("list", "hubspot") == "I can't search HubSpot lists yet."
    assert cant_search_yet("file", "dropbox") == "I can't search Dropbox files yet."


# --- Outlook participants --------------------------------------------------------


def _graph(frm: tuple[str, str], to: list[tuple[str, str]], *, draft: bool = False, other: bool = False) -> dict[str, Any]:
    def person(p: tuple[str, str]) -> dict[str, Any]:
        return {"emailAddress": {"name": p[0], "address": p[1]}}

    return {
        "from": person(frm),
        "toRecipients": [person(p) for p in to],
        "isDraft": draft,
        "inferenceClassification": "other" if other else "focused",
        "receivedDateTime": "2026-10-01T10:00:00Z",
    }


ME_OUT = ("Stephanie Lane", "stephanie.lane@contoso.example")


@pytest.mark.asyncio
async def test_outlook_finds_people_and_leaves_out_the_user_and_noise(reads) -> None:
    fake = reads(
        {
            "microsoft365.users.get": {"user": {"mail": ME_OUT[1]}},
            "microsoft365.mail.messages.list": {
                "value": [
                    _graph(("Stephanie Khan", "sk@acme.example"), [ME_OUT]),
                    _graph(ME_OUT, [("Stephanie Khan", "sk@acme.example")]),
                    _graph(("Stephanie at Promo", "news@promo.example"), [ME_OUT], other=True),
                    _graph(("Stephanie Wu", "no-reply@tracker.example"), [ME_OUT]),
                ]
            },
        }
    )
    res = await resolve_outlook_participant("Stephanie", connected=["microsoft365"], **_kw())
    assert res.status == "resolved" and res.chosen.address == "sk@acme.example"
    assert res.chosen.source == "microsoft365" and res.chosen.evidence["sent"] == 1
    listed = next(p for a, p in fake.calls if a == "microsoft365.mail.messages.list")
    assert listed["search"] == "participants:Stephanie"
    assert all(a in {"microsoft365.users.get", "microsoft365.mail.messages.list"} for a, _p in fake.calls)


@pytest.mark.asyncio
async def test_outlook_more_results_means_incomplete(reads) -> None:
    reads(
        {
            "microsoft365.users.get": {"user": {"mail": ME_OUT[1]}},
            "microsoft365.mail.messages.list": {
                "value": [_graph(("Stephanie Khan", "sk@acme.example"), [ME_OUT])],
                "@odata.nextLink": "https://graph.example/next",
            },
        }
    )
    res = await resolve_outlook_participant("Stephanie", connected=["microsoft365"], **_kw())
    assert res.status == "incomplete" and res.candidates[0].address == "sk@acme.example"


@pytest.mark.asyncio
async def test_outlook_drafts_and_failures(reads) -> None:
    reads(
        {
            "microsoft365.users.get": {"user": {"mail": ME_OUT[1]}},
            "microsoft365.mail.messages.list": {"value": [_graph(ME_OUT, [("Stephanie Park", "sp@initech.example")], draft=True)]},
        }
    )
    res = await resolve_outlook_participant("Stephanie", connected=["microsoft365"], **_kw())
    assert (res.status, res.reason) == ("ambiguous", "draft_only")
    reads({"microsoft365.users.get": "auth_expired", "microsoft365.mail.messages.list": "permission_denied"})
    failed = await resolve_outlook_participant("Stephanie", connected=["microsoft365"], **_kw())
    assert (failed.status, failed.reason) == ("unavailable", "permission")
    off = await resolve_outlook_participant("Stephanie", connected=["gmail"], **_kw())
    assert (off.status, off.reason) == ("unavailable", "not_connected")


# --- CRM contacts ----------------------------------------------------------------


def _hs(cid: str, first: str, last: str, email: str, company: str = "") -> dict[str, Any]:
    return {"id": cid, "properties": {"firstname": first, "lastname": last, "email": email, "company": company}}


@pytest.mark.asyncio
async def test_hubspot_contacts(reads) -> None:
    db = _db({"id": "hs-1", "type": "hubspot", "config": {"display_name": "Acme portal"}})
    fake = reads(
        {
            "hubspot.contacts.search": {
                "contacts": [
                    _hs("101", "Stephanie", "Khan", "sk@acme.example"),
                    _hs("102", "Stephanie", "Wu", "swu@globex.example"),
                    _hs("103", "Pat", "Lee", "pat@stephanie-designs.example", company="Stephanie Designs"),
                ],
                "total": 3,
            }
        }
    )
    res = await resolve_crm_contact("Stephanie", source="hubspot", connected=["hubspot"], **_kw(db))
    assert res.status == "ambiguous"
    assert [(c.object_id, c.object_type, c.account) for c in res.candidates] == [("101", "contact", "hs-1"), ("102", "contact", "hs-1")]
    assert fake.calls[0][1]["connector_id"] == "hs-1"
    exact = await resolve_crm_contact("Stephanie Wu", source="hubspot", connected=["hubspot"], **_kw(db))
    assert exact.status == "resolved" and exact.chosen.object_id == "102"


@pytest.mark.asyncio
async def test_hubspot_more_matches_than_returned_is_incomplete(reads) -> None:
    reads({"hubspot.contacts.search": {"contacts": [_hs("101", "Stephanie", "Khan", "sk@acme.example")], "total": 40}})
    res = await resolve_crm_contact("Stephanie", source="hubspot", connected=["hubspot"], **_kw())
    assert res.status == "incomplete"


@pytest.mark.asyncio
async def test_salesforce_contacts(reads) -> None:
    reads(
        {
            "salesforce.contacts.search": {
                "results": {
                    "records": [{"Id": "003A", "Name": "Stephanie Khan", "Email": "sk@acme.example", "AccountId": "001A"}],
                    "totalSize": 1,
                    "done": True,
                }
            }
        }
    )
    res = await resolve_crm_contact("Stephanie", source="salesforce", connected=["salesforce"], **_kw())
    assert res.status == "resolved" and res.chosen.object_id == "003A" and res.chosen.address == "sk@acme.example"
    reads({"salesforce.contacts.search": {"results": {"records": [{"Id": "003A", "Name": "Stephanie Khan"}], "totalSize": 300, "done": False}}})
    more = await resolve_crm_contact("Stephanie", source="salesforce", connected=["salesforce"], **_kw())
    assert more.status == "incomplete"


@pytest.mark.asyncio
async def test_unsupported_crm_is_unavailable_without_a_read(reads) -> None:
    fake = reads({})
    res = await resolve_crm_contact("Stephanie", source="pipedrive", connected=["pipedrive"], **_kw())
    assert (res.status, res.reason) == ("unavailable", "capability_missing")
    assert fake.calls == []


# --- lists and segments ------------------------------------------------------------


@pytest.mark.asyncio
async def test_apollo_lists(reads) -> None:
    reads({"apollo.lists.list": {"labels": [{"id": "L1", "name": "MSP"}, {"id": "L2", "name": "MSP Prospects", "cached_count": 40}, {"id": "L3", "name": "Renewals"}]}})
    exact = await resolve_list("the MSP list", source="apollo", connected=["apollo"], **_kw())
    assert exact.status == "resolved" and exact.chosen.object_id == "L1"
    one = await resolve_list("prospects", source="apollo", connected=["apollo"], **_kw())
    assert one.status == "resolved" and one.chosen.object_id == "L2" and one.chosen.evidence["members"] == 40
    none = await resolve_list("Churned", source="apollo", connected=["apollo"], **_kw())
    assert none.status == "not_found"


@pytest.mark.asyncio
async def test_constant_contact_lists_and_segments(reads) -> None:
    reads(
        {
            "constant_contact.contact_lists.list": {
                "lists": [{"list_id": "a", "name": "Renewal customers"}, {"list_id": "b", "name": "Renewal prospects"}],
                "_links": {"next": {"href": "/v3/contact_lists?cursor=x"}},
            },
            "constant_contact.segments.list": {"segments": [{"segment_id": 7, "name": "Renewal segment"}]},
        }
    )
    lists = await resolve_list("renewal", source="constant_contact", connected=["constant_contact"], **_kw())
    assert lists.status == "ambiguous"
    seg = await resolve_list("renewal", source="constant_contact", object_type="segment", connected=["constant_contact"], **_kw())
    assert seg.status == "resolved" and seg.chosen.object_id == "7" and seg.chosen.object_type == "segment"


@pytest.mark.asyncio
@pytest.mark.parametrize(("source", "object_type"), [("hubspot", "list"), ("mailchimp", "list"), ("hubspot", "segment"), ("klaviyo", "list")])
async def test_lists_we_cannot_search_say_so(reads, source: str, object_type: str) -> None:
    fake = reads({})
    res = await resolve_list("MSP", source=source, object_type=object_type, connected=[source], **_kw())
    assert (res.status, res.reason) == ("unavailable", "capability_missing")
    assert fake.calls == []


# --- files ----------------------------------------------------------------------------


def _hit(fid: str, name: str, mime: str, modified: str, path: str = "", source: str = "google_drive") -> dict[str, Any]:
    return {"vendor": source, "file_id": fid, "name": name, "mime_type": mime, "modified_at": modified, "web_link": f"https://files.example/{fid}", "path": path or name}


SHEET = "application/vnd.google-apps.spreadsheet"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOC = "application/vnd.google-apps.document"


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Send Stephanie the budget spreadsheet", ("budget spreadsheet", "budget", "spreadsheet")),
        ("Send Stephanie Khan the Q3 board deck on Gmail", ("Q3 board deck", "Q3 board", "presentation")),
        ("Email the budget sheet to Stephanie", ("budget sheet", "budget", "spreadsheet")),
        ("Send Stephanie an email", None),
        ("Send Stephanie the update", None),  # no file word: not a file request
        ("Send an email to Stephanie and attach the pricing pdf", ("pricing pdf", "pricing", "pdf")),
    ],
)
def test_extract_file_request(message: str, expected: tuple[str, str, str] | None) -> None:
    req = extract_file_request(message)
    assert ((req.phrase, req.query, req.kind) if req else None) == expected


@pytest.mark.asyncio
async def test_drive_files_are_matched_by_title_and_kind(reads) -> None:
    fake = reads(
        {
            "google_drive.search_files": {
                "files": [
                    _hit("f1", "Budget 2026", SHEET, "2026-10-03T12:00:00Z", "Finance/Budget 2026"),
                    _hit("f2", "Budget 2026", SHEET, "2026-09-12T12:00:00Z", "Drafts/Budget 2026"),
                    _hit("f3", "Budget notes", DOC, "2026-10-01T12:00:00Z"),
                    _hit("f4", "Q3 report", DOC, "2026-10-02T12:00:00Z"),  # matched on content only
                ]
            }
        }
    )
    res = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), connected=["google_drive"], **_kw())
    assert res.status == "ambiguous" and [c.object_id for c in res.candidates] == ["f1", "f2"]
    assert file_question(res) == (
        'I found two files that match "budget spreadsheet": Budget 2026 (in Finance, modified Oct 3, 2026) '
        "and Budget 2026 (in Drafts, modified Sep 12, 2026). Which one?"
    )
    assert fake.calls == [("google_drive.search_files", {"query": "budget", "page_size": obr.SEARCH_PAGE_SIZE})]


@pytest.mark.asyncio
async def test_files_across_drive_and_onedrive_say_where(reads) -> None:
    reads(
        {
            "google_drive.search_files": {"files": [_hit("g1", "Budget 2026", SHEET, "2026-10-03")]},
            "microsoft365.search_files": {"files": [_hit("o1", "Budget 2026.xlsx", XLSX, "2026-10-04", source="microsoft365")]},
        }
    )
    res = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), connected=["google_drive", "microsoft365"], **_kw())
    assert res.status == "ambiguous"
    assert "Budget 2026.xlsx (on OneDrive)" in file_question(res) and "Budget 2026 (on Google Drive)" in file_question(res)


@pytest.mark.asyncio
async def test_a_full_page_of_files_is_incomplete(reads) -> None:
    rows = [_hit("f0", "Budget 2026", SHEET, "2026-10-03")] + [_hit(f"x{i}", f"Other {i}", DOC, "2026-01-01") for i in range(obr.SEARCH_PAGE_SIZE - 1)]
    reads({"google_drive.search_files": {"files": rows}})
    res = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), connected=["google_drive"], **_kw())
    assert res.status == "incomplete" and res.candidates[0].object_id == "f0"


@pytest.mark.asyncio
async def test_file_sources_missing_or_failing(reads) -> None:
    none = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), connected=["gmail"], **_kw())
    assert (none.status, none.reason) == ("unavailable", "not_connected")
    reads({"google_drive.search_files": "auth_expired"})
    failed = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), connected=["google_drive"], **_kw())
    assert (failed.status, failed.reason) == ("unavailable", "permission")


def test_file_access_is_a_metadata_read_for_the_same_account(reads) -> None:
    fake = reads({"google_drive.get_file_metadata": {"file": {"file_id": "f1", "web_link": "https://files.example/f1-new"}}})
    cand = _cand("Budget 2026", object_id="f1", object_type="file", source="google_drive", account="drive-1")
    checked, calls = verify_file_access_sync(cand, **_kw())
    assert checked.access == "ok" and checked.evidence["web_link"] == "https://files.example/f1-new" and calls == 1
    assert fake.calls == [("google_drive.get_file_metadata", {"file_id": "f1", "connector_id": "drive-1"})]
    reads({"google_drive.get_file_metadata": {"file": {"file_id": "someone-else"}}})
    assert verify_file_access_sync(cand, **_kw())[0].access == "denied"
    reads({"google_drive.get_file_metadata": "auth_expired"})
    assert verify_file_access_sync(cand, **_kw())[0].access == "denied"


def test_revalidate_bound_targets_before_execution(reads) -> None:
    from types import SimpleNamespace

    ctx = SimpleNamespace(org_id=ORG, client=ScenarioDB(), settings=object(), actor_id="", conversation_id=None)
    assert revalidate_bound_targets(ctx, {"to": "sk@acme.example"}) == ""
    args = {"file_id": "f1", "file_source": "google_drive", "file_account": "drive-1", "file_name": "Budget 2026"}
    reads({"google_drive.get_file_metadata": {"file": {"file_id": "f1"}}})
    assert revalidate_bound_targets(ctx, args) == ""
    reads({"google_drive.get_file_metadata": "permission_denied"})
    assert revalidate_bound_targets(ctx, args) == (
        "I can't open Budget 2026 with your Google Drive account anymore, so I didn't send the email. Nothing was sent."
    )


def test_a_file_goes_in_as_a_link_and_the_prompt_says_so() -> None:
    params = {"file_id": "f1", "file_source": "google_drive", "file_name": "Budget 2026", "file_link": "https://files.example/f1"}
    assert body_with_file_link("Numbers attached.", params) == "Numbers attached.\n\nBudget 2026: https://files.example/f1"
    assert body_with_file_link("See https://files.example/f1", params) == "See https://files.example/f1"
    assert body_with_file_link("Hi", {}) == "Hi"
    assert file_approval_line(params) == "Budget 2026 on Google Drive, added as a link (attachments aren't supported yet)"


# --- connector extensions -------------------------------------------------------------


def test_gmail_list_messages_passes_the_page_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.connectors import gmail

    seen: dict[str, Any] = {}
    monkeypatch.setattr(gmail, "_request", lambda _t, _m, _p, **kw: seen.update(kw) or {})
    gmail.list_messages("tok", query="from:x", max_results=25, page_token="abc", label_ids=["INBOX"])
    assert seen["params"] == {"maxResults": 25, "q": "from:x", "pageToken": "abc", "labelIds": ["INBOX"]}


def test_outlook_search_drops_orderby(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.connectors.microsoft365 as m365

    seen: dict[str, Any] = {}
    monkeypatch.setattr(m365, "_request", lambda _t, _m, _p, **kw: seen.update(kw) or {})
    m365.list_mail_messages("tok", top=50, search="participants:Stephanie")
    assert seen["params"] == {"$top": 50, "$search": '"participants:Stephanie"'}
    m365.list_mail_messages("tok", top=10)
    assert seen["params"] == {"$top": 10, "$orderby": "receivedDateTime desc"}


def test_gmail_send_appends_the_approved_link(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.tool_service as ts
    from app.connectors import gmail

    sent: dict[str, Any] = {}
    monkeypatch.setattr(ts, "_google_vendor_token", lambda *_a, **_k: ("conn-gmail", "tok"))
    monkeypatch.setattr(gmail, "send_message", lambda _t, **kw: sent.update(kw) or {"id": "m1"})
    ts._exec_gmail_messages_send(
        None,
        {"to": "sk@acme.example", "subject": "Budget", "body": "Here it is.", "file_id": "f1", "file_name": "Budget 2026", "file_link": "https://files.example/f1"},
    )
    assert sent["body"] == "Here it is.\n\nBudget 2026: https://files.example/f1"


# --- the email grounding on Outlook ------------------------------------------------------


@pytest.mark.asyncio
async def test_an_outlook_send_grounds_its_recipient_with_the_same_contract(reads) -> None:
    from dataclasses import dataclass

    from app.services.chat_connector_models import ConnectorActionPlan

    @dataclass
    class Clarification:
        message: str
        dialogue_mode: str = "clarify"
        status: str = "awaiting_params"

    from app.services.recipient_resolution import apply_resolution_to_stage, ground_email_recipient

    reads(
        {
            "microsoft365.users.get": {"user": {"mail": ME_OUT[1]}},
            "microsoft365.mail.messages.list": {
                "value": [
                    _graph(("Stephanie Khan", "sk@acme.example"), [ME_OUT]),
                    _graph(("Stephanie Wu", "swu@globex.example"), [ME_OUT]),
                ]
            },
        }
    )
    plan = ConnectorActionPlan(
        tool_name="microsoft365_mail_send",
        invoke_action="microsoft365.mail.send",
        integration="microsoft365",
        kind="write",
        label="Send email",
        args={"to": "stephanie@invented.example"},
    )
    grounded, found = await ground_email_recipient(
        plan, "Email Stephanie on Outlook", {}, connected_integrations=["microsoft365"], **_kw()
    )
    assert "to" not in grounded.args, "an invented address survived"
    assert found.recipient.status == "ambiguous" and found.recipient.source == "microsoft365"

    staged = (
        Clarification(message="Who should it go to?"),
        {"pending_task": {"params": {"args": {}}}},
    )
    clarification, patch = apply_resolution_to_stage(staged, found)
    assert clarification.message == "I found two Stephanies: Stephanie Khan and Stephanie Wu. Which one?"
    assert [c["source"] for c in patch["recipient_candidates"]] == ["microsoft365", "microsoft365"]


@pytest.mark.asyncio
async def test_an_outlook_choice_sends_from_the_mailbox_that_was_searched() -> None:
    import time

    from app.services import recipient_resolution as rr

    work = obr.Account(id="outlook-work", vendor="microsoft365", label="work", stamp="s1")
    home = obr.Account(id="outlook-home", vendor="microsoft365", label="home", stamp="s2")
    offered = [
        obr.ResolutionCandidate(
            name=name,
            address=addr,
            source="microsoft365",
            account="outlook-work",
            account_stamp="s1",
            object_type="person",
            object_id=addr,
            resolved_at=time.time(),
        ).to_dict()
        for name, addr in (("Stephanie Khan", "sk@acme.example"), ("Stephanie Wu", "swu@globex.example"))
    ]
    state = {"pending_task": {"status": "awaiting_params"}, rr.CANDIDATES_KEY: offered}
    args: dict = {}
    res = await rr._ground_recipient(
        "microsoft365",
        args,
        "Khan",
        state,
        accounts=[home, work],
        account=None,
        how="default",
        lookup_kwargs={},
    )
    assert res is not None and res.status == "resolved"
    assert args == {"to": "sk@acme.example", "connector_id": "outlook-work"}
